"""Hive — lightweight MCP-over-HTTP client for cortex-hub.

Speaks the hub's StreamableHTTP protocol using only stdlib. Used by
the distiller for --hive-push / --hive-pull / --hive-status, and by the
MCP server for real-time hive proxying.

Protocol:
  1. POST /mcp  {initialize}        -> response headers contain mcp-session-id
  2. POST /mcp  {notifications/initialized}  -> no response body
  3. POST /mcp  {tools/call}         -> SSE text body, parse data: lines

Dependencies: stdlib only (urllib.request, json, uuid, time, logging).
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

log = logging.getLogger("hive_client")


class HubConnectionError(Exception):
    """Raised when the hub is unreachable or returns an error."""


class HubClient:
    """Connect to a cortex-hub MCP server and call tools."""

    def __init__(
        self,
        url: str,
        token: str = "",
        timeout: int = 10,
        max_retries: int = 5,
    ):
        self.url = url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.max_retries = max_retries
        self.session_id: str | None = None
        self.retry_count = 0
        self._closing = False

    def connect(self) -> None:
        """MCP initialize handshake. Extracts session ID from response headers."""
        resp = self._raw_post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "cortex-hive", "version": "1.0.0"},
                },
            }
        )
        self.session_id = resp["headers"].get("mcp-session-id")
        if not self.session_id:
            raise HubConnectionError(
                f"Hub did not return mcp-session-id. Is this really an MCP server at {self.url}?"
            )
        # Send initialized notification (no id field — it's a notification)
        self._raw_post(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }
        )

    def call_tool(self, name: str, args: dict[str, Any] | None = None) -> Any:
        """Call an MCP tool on the hub. Returns parsed result content."""
        try:
            resp = self._raw_post(
                {
                    "jsonrpc": "2.0",
                    "id": str(uuid.uuid4()),
                    "method": "tools/call",
                    "params": {"name": name, "arguments": args or {}},
                }
            )
            for msg in self._parse_sse(resp["body"]):
                if "error" in msg:
                    raise HubConnectionError(f"Hub tool error on {name}: {msg['error']}")
                if "result" in msg:
                    content = msg["result"].get("content", [])
                    if content and content[0].get("text"):
                        text = content[0]["text"]
                        try:
                            return json.loads(text)
                        except (json.JSONDecodeError, ValueError):
                            return text
            return None
        except HubConnectionError:
            if not self._closing:
                return self._reconnect_and_retry(name, args)
            raise

    def memory_set(self, key: str, value: str, tags: list[str] | None = None) -> Any:
        """Store a memory on the hub."""
        return self.call_tool(
            "hub_memory_set",
            {
                "key": key,
                "value": value,
                "tags": tags or [],
                "agent": "cortex",
            },
        )

    def memory_get(self, key: str) -> Any:
        """Retrieve a memory by key."""
        return self.call_tool("hub_memory_get", {"key": key})

    def memory_search(self, query: str) -> list[dict] | None:
        """Search memories by content, key, or tags."""
        result = self.call_tool("hub_memory_search", {"query": query})
        return result if isinstance(result, list) else None

    def close(self) -> None:
        self._closing = True
        self.session_id = None

    # --- Internal ---

    def _reconnect_and_retry(self, name: str, args: dict[str, Any] | None) -> Any:
        """Reconnect to the hub and retry the failed tool call."""
        if self.retry_count >= self.max_retries:
            raise HubConnectionError(f"Max retries ({self.max_retries}) exceeded")

        self.retry_count += 1
        delay_ms = min(1000 * (2 ** (self.retry_count - 1)), 30_000)
        log.warning(
            "Connection lost, reconnecting (retry %d/%d, delay %dms)...",
            self.retry_count,
            self.max_retries,
            delay_ms,
        )

        time.sleep(delay_ms / 1000)
        self.session_id = None

        try:
            self.connect()
            self.retry_count = 0
            return self.call_tool(name, args)
        except HubConnectionError:
            return self._reconnect_and_retry(name, args)

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            h["mcp-session-id"] = self.session_id
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _raw_post(self, body: dict) -> dict[str, Any]:
        """POST to the hub. Returns {body: str, headers: dict}."""
        data = json.dumps(body).encode("utf-8")
        headers = {**self._headers(), "Content-Length": str(len(data))}
        req = urllib.request.Request(self.url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp_headers = dict(resp.headers)
                resp_body = resp.read().decode("utf-8")
        except urllib.error.URLError as e:
            raise HubConnectionError(f"Cannot reach hub at {self.url}: {e}") from e
        except OSError as e:
            raise HubConnectionError(f"Network error connecting to hub: {e}") from e
        return {"body": resp_body, "headers": resp_headers}

    @staticmethod
    def _parse_sse(text: str) -> list[dict]:
        """Parse SSE text into a list of JSON-RPC messages."""
        results = []
        for line in text.split("\n"):
            if line.startswith("data: "):
                try:
                    results.append(json.loads(line[6:]))
                except (json.JSONDecodeError, ValueError):
                    pass
        if not results:
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    results.append(parsed)
            except (json.JSONDecodeError, ValueError):
                pass
        return results

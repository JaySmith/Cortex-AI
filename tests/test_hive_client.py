"""Tests for cortex.hub.client — SSE parsing and client helpers."""

import json

import pytest

from cortex.hub.client import HubClient, HubConnectionError

# ---------------------------------------------------------------------------
# _parse_sse (static method — pure text parsing)
# ---------------------------------------------------------------------------


class TestParseSse:
    def test_single_data_line(self):
        msg = json.dumps({"jsonrpc": "2.0", "id": "1", "result": {"content": []}})
        text = f"data: {msg}\n\n"
        results = HubClient._parse_sse(text)
        assert len(results) == 1
        assert results[0]["id"] == "1"

    def test_multiple_data_lines(self):
        m1 = json.dumps({"jsonrpc": "2.0", "id": "1", "result": {}})
        m2 = json.dumps({"jsonrpc": "2.0", "id": "2", "result": {}})
        text = f"data: {m1}\n\ndata: {m2}\n\n"
        results = HubClient._parse_sse(text)
        assert len(results) == 2

    def test_non_data_lines_ignored(self):
        text = "event: message\ndata: some json\n\n"
        results = HubClient._parse_sse(text)
        # "some json" is invalid JSON so it's silently skipped; event line isn't a data: line
        assert results == []

    def test_empty_text(self):
        results = HubClient._parse_sse("")
        assert results == []

    def test_bare_json_fallback(self):
        msg = json.dumps({"jsonrpc": "2.0", "id": "1", "result": {}})
        results = HubClient._parse_sse(msg)
        assert len(results) == 1

    def test_malformed_data_line(self):
        text = "data: NOT VALID JSON\n\n"
        results = HubClient._parse_sse(text)
        assert results == []

    def test_mixed_valid_invalid(self):
        valid = json.dumps({"id": "1"})
        text = f"data: bad json\ndata: {valid}\n\n"
        results = HubClient._parse_sse(text)
        assert len(results) == 1
        assert results[0]["id"] == "1"


# ---------------------------------------------------------------------------
# HubClient construction
# ---------------------------------------------------------------------------


class TestHubClientInit:
    def test_strips_trailing_slash(self):
        client = HubClient("http://example.com/mcp/")
        assert client.url == "http://example.com/mcp"

    def test_defaults(self):
        client = HubClient("http://example.com")
        assert client.token == ""
        assert client.timeout == 10
        assert client.max_retries == 5
        assert client.session_id is None
        assert client.retry_count == 0

    def test_custom_params(self):
        client = HubClient("http://example.com", token="abc", timeout=30, max_retries=3)
        assert client.token == "abc"
        assert client.timeout == 30
        assert client.max_retries == 3


# ---------------------------------------------------------------------------
# _headers
# ---------------------------------------------------------------------------


class TestHeaders:
    def test_base_headers(self):
        client = HubClient("http://example.com")
        h = client._headers()
        assert h["Content-Type"] == "application/json"
        assert "Accept" in h
        assert "mcp-session-id" not in h
        assert "Authorization" not in h

    def test_with_session(self):
        client = HubClient("http://example.com")
        client.session_id = "sess-123"
        h = client._headers()
        assert h["mcp-session-id"] == "sess-123"

    def test_with_token(self):
        client = HubClient("http://example.com", token="tok-abc")
        h = client._headers()
        assert h["Authorization"] == "Bearer tok-abc"

    def test_close_clears_session(self):
        client = HubClient("http://example.com")
        client.session_id = "sess-123"
        client.close()
        assert client.session_id is None


# ---------------------------------------------------------------------------
# _reconnect_and_retry limits
# ---------------------------------------------------------------------------


class TestReconnectRetry:
    def test_raises_after_max_retries(self):
        client = HubClient("http://example.com", max_retries=2)
        client.retry_count = 3
        with pytest.raises(HubConnectionError, match="Max retries"):
            client._reconnect_and_retry("test_tool", {})

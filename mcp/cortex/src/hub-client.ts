/**
 * hub-client.ts — Lightweight MCP-over-HTTP client for cortex-hub.
 *
 * Speaks the hub's StreamableHTTP protocol using Node.js fetch.
 * Used by the MCP server for real-time hive proxying.
 *
 * Protocol:
 *   1. POST /mcp  {initialize}                → session ID in response header
 *   2. POST /mcp  {notifications/initialized}  → no response body
 *   3. POST /mcp  {tools/call}                 → SSE text body, parse data: lines
 */

export interface HubClientConfig {
  url: string;
  token?: string;
  timeout?: number;
}

export class HubClient {
  private url: string;
  private token: string;
  private timeout: number;
  private sessionId: string | null = null;

  constructor(config: HubClientConfig) {
    this.url = config.url.replace(/\/+$/, "");
    this.token = config.token ?? "";
    this.timeout = config.timeout ?? 10_000;
  }

  /** MCP initialize handshake. Extracts session ID from response headers. */
  async connect(): Promise<void> {
    const resp = await this.rawPost({
      jsonrpc: "2.0",
      id: 1,
      method: "initialize",
      params: {
        protocolVersion: "2025-03-26",
        capabilities: {},
        clientInfo: { name: "cortex-hive", version: "1.0.0" },
      },
    });
    this.sessionId = resp.headers.get("mcp-session-id");
    if (!this.sessionId) {
      throw new Error(
        `Hub did not return mcp-session-id. Is this really an MCP server at ${this.url}?`,
      );
    }
    // Send initialized notification (no id field — it's a notification)
    await this.rawPost({
      jsonrpc: "2.0",
      method: "notifications/initialized",
    });
  }

  /** Call an MCP tool on the hub. Returns parsed result content. */
  async callTool(name: string, args: Record<string, unknown> = {}): Promise<unknown> {
    const resp = await this.rawPost({
      jsonrpc: "2.0",
      id: crypto.randomUUID(),
      method: "tools/call",
      params: { name, arguments: args },
    });
    const text = await resp.text();
    for (const msg of this.parseSse(text)) {
      if ("error" in msg) {
        throw new Error(`Hub tool error on ${name}: ${JSON.stringify(msg.error)}`);
      }
      if ("result" in msg) {
        const content = (msg.result as { content?: Array<{ type: string; text?: string }> }).content;
        if (content?.[0]?.text) {
          try {
            return JSON.parse(content[0].text);
          } catch {
            return content[0].text;
          }
        }
      }
    }
    return null;
  }

  async memorySet(key: string, value: string, tags: string[] = []): Promise<unknown> {
    return this.callTool("hub_memory_set", { key, value, tags, agent: "cortex" });
  }

  async memoryGet(key: string): Promise<unknown> {
    return this.callTool("hub_memory_get", { key });
  }

  async memorySearch(query: string): Promise<unknown> {
    return this.callTool("hub_memory_search", { query });
  }

  close(): void {
    this.sessionId = null;
  }

  // --- Internal ---

  private headers(): Record<string, string> {
    const h: Record<string, string> = {
      "Content-Type": "application/json",
      Accept: "application/json, text/event-stream",
    };
    if (this.sessionId) {
      h["mcp-session-id"] = this.sessionId;
    }
    if (this.token) {
      h["Authorization"] = `Bearer ${this.token}`;
    }
    return h;
  }

  private async rawPost(body: Record<string, unknown>): Promise<Response> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeout);
    try {
      const resp = await fetch(this.url, {
        method: "POST",
        headers: this.headers(),
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      return resp;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      throw new Error(`Cannot reach hub at ${this.url}: ${msg}`);
    } finally {
      clearTimeout(timer);
    }
  }

  private parseSse(text: string): Record<string, unknown>[] {
    const results: Record<string, unknown>[] = [];
    for (const line of text.split("\n")) {
      if (line.startsWith("data: ")) {
        try {
          results.push(JSON.parse(line.slice(6)));
        } catch {
          // skip unparseable lines
        }
      }
    }
    // Also try parsing the whole body as JSON (non-SSE responses)
    if (results.length === 0) {
      try {
        const parsed = JSON.parse(text);
        if (typeof parsed === "object" && parsed !== null) {
          results.push(parsed);
        }
      } catch {
        // not JSON — that's fine
      }
    }
    return results;
  }
}

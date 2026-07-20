# Hive Integration Plan: cortex-ai + cortex-hub

**Status:** Approved, ready for implementation
**Last updated:** 2026-07-12

## Overview

cortex-ai is a single-machine vault encoder. cortex-hub is a multi-agent coordination layer with shared memory and messaging. This plan makes them work together: cortex-ai is the **brain** (vault, tiers, encoding, structured memory), cortex-hub is the **nervous system** (agent registry, messaging, shared memory store).

## Repository Ownership

These are **separate repos**. The integration is via HTTP, not shared code.

| Repo | What lives here | Integration surface |
|---|---|---|
| `cortex-ai` | vault encoder, MCP server, skills, **this plan** | Python hub client (`cortex.hub.client`) calls hub HTTP API |
| `cortex-hub` | hub MCP server, agent-sdk, daemon agents | Bearer auth middleware (Phase 7), existing `hub_memory_*` tools |

**Phase ownership:**

| Phase | Repo | Change |
|---|---|---|
| Phase 1: Config + migration | cortex-ai | Config parsing, schema bump |
| Phase 2: Python hub client | cortex-ai | New module `cortex/hub/client.py` |
| Phase 3: CLI commands | cortex-ai | `--hive-push/pull/status` |
| Phase 4: Hive frontmatter | cortex-ai | `VaultNote.hive` field |
| Phase 5: MCP server proxy | cortex-ai | TypeScript hub client in MCP server |
| Phase 6: Skill commands | cortex-ai | `cortex hive` subcommands |
| Phase 7: Bearer token auth | **cortex-hub** | Express middleware + cortex-ai config |

**Stable contract:** The hub's `hub_memory_*` MCP tools are the API. No shared code, no shared types. The Python client calls them over HTTP.

## Decisions (locked)

| Decision | Choice |
|---|---|
| Hub client language | Python (note future TypeScript need for real-time MCP proxy) |
| Conflict resolution | Newest `updated` timestamp wins; section-aware merge deferred |
| Bearer token auth | After hive integration (phase 7+) |
| Machine ID format | Config-friendly name (e.g. `office-desktop`, `laptop`) |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Machine A                                                     │
│  ┌──────────────┐    MCP (stdio)    ┌───────────────────────┐  │
│  │  Agent        │◄────────────────►│  cortex-ai MCP server │  │
│  │  (opencode)   │                  │  (local + hive proxy) │  │
│  └──────────────┘                   └──────────┬────────────┘  │
│                                                │               │
│                                    HTTP (MCP over SSE)         │
│                                                │               │
│  ┌─────────────────────────────────────────────▼──────────┐    │
│  │              cortex-hub MCP server (port 4096)          │    │
│  │  SQLite: memories + agents + messages                   │    │
│  │  vault/* keys = shared vault notes                      │    │
│  └─────────────────────────────────────────────▲──────────┘    │
│                                    HTTP (MCP over SSE)         │
│                                                │               │
│  ┌──────────────┐    MCP (stdio)    ┌──────────┴────────────┐  │
│  │  Agent        │◄────────────────►│  cortex-ai MCP server │  │
│  │  (opencode)   │                  │  (local + hive proxy) │  │
│  └──────────────┘                   └───────────────────────┘  │
│  Machine B                                                     │
└─────────────────────────────────────────────────────────────────┘
```

Key behaviors:
1. Each machine runs its own cortex-ai MCP server (stdio, local to opencode).
2. Each cortex-ai server optionally connects to a shared cortex-hub (HTTP).
3. On `memory_write` with `hive: true` (or tier matching), the local server pushes to the hub.
4. On `memory_search`, the local server merges local + hub results.
5. `cortex encode --hive-push` / `--hive-pull` handle bulk sync for the CLI workflow.
6. The hub is the write authority — conflicts resolve by `updated` timestamp (newest wins).

---

## Phase 1: Config + Schema Migration

**Files to change:**
- `cortex.yaml.example` — add `hive:` block
- `cortex/encoder/core.py` — parse new `hive:` config keys, bump `SCHEMA_VERSION` to 2, add migration
- `SCHEMA_VERSION` file — `1` → `2`

**cortex.yaml additions:**
```yaml
hive:
  enabled: false
  hub_url: "http://localhost:4096/mcp"
  machine_id: ""            # e.g. "office-desktop", "laptop"
  replicate_tiers:
    - core
    - "skill:*"
    - project
  sync_interval: 300        # seconds, 0 = manual only
```

**cortex/encoder/core.py changes:**
- `load_config()` — parse `hive:` section with defaults
- `check_and_migrate()` — v1→v2 migration: add `hive.enabled: false` to existing config, backup `_sync/` first
- `--show-config` — add `hive_enabled`, `hive_hub_url`, `hive_machine_id` fields

---

## Phase 2: Python Hub Client

**Module:** `cortex/hub/client.py` (~120 lines)

A minimal Python HTTP client that speaks the hub's MCP-over-HTTP protocol.

```python
"""hive_client.py — Lightweight MCP-over-HTTP client for cortex-hub."""

import json
import uuid
import urllib.request


class HubClient:
    """Connect to a cortex-hub MCP server and call tools."""

    def __init__(self, url: str, token: str = ""):
        self.url = url.rstrip("/")
        self.token = token
        self.session_id = None

    def connect(self):
        """MCP initialize handshake, extract session ID."""
        resp = self._raw_post({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "cortex-hive", "version": "1.0.0"},
            },
        })
        self.session_id = resp["headers"].get("mcp-session-id")
        if not self.session_id:
            raise RuntimeError("Hub did not return mcp-session-id")
        # Send initialized notification
        self._raw_post({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        })

    def call_tool(self, name: str, args: dict = None) -> dict:
        """Call an MCP tool on the hub. Returns parsed result."""
        resp = self._raw_post({
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "tools/call",
            "params": {"name": name, "arguments": args or {}},
        })
        for msg in self._parse_sse(resp["body"]):
            if "result" in msg:
                content = msg["result"].get("content", [])
                if content and content[0].get("text"):
                    try:
                        return json.loads(content[0]["text"])
                    except (json.JSONDecodeError, IndexError):
                        return content[0]["text"]
        return None

    def memory_set(self, key: str, value: str, tags: list = None):
        return self.call_tool("hub_memory_set", {
            "key": key, "value": value,
            "tags": tags or [], "agent": "cortex",
        })

    def memory_get(self, key: str):
        return self.call_tool("hub_memory_get", {"key": key})

    def memory_search(self, query: str):
        return self.call_tool("hub_memory_search", {"query": query})

    def close(self):
        self.session_id = None

    # --- Internal ---

    def _headers(self):
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.session_id:
            h["mcp-session-id"] = self.session_id
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _raw_post(self, body: dict) -> dict:
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            self.url,
            data=data,
            headers={**self._headers(), "Content-Length": str(len(data))},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            headers = dict(resp.headers)
            body_text = resp.read().decode()
        return {"body": body_text, "headers": headers}

    @staticmethod
    def _parse_sse(text: str) -> list:
        results = []
        for line in text.split("\n"):
            if line.startswith("data: "):
                try:
                    results.append(json.loads(line[6:]))
                except (json.JSONDecodeError, ValueError):
                    pass
        return results
```

**Protocol details (from cortex-hub source):**
1. `POST /mcp` with `initialize` JSON-RPC → response headers contain `mcp-session-id`
2. `POST /mcp` with `notifications/initialized` (no `id` field)
3. `POST /mcp` with `tools/call` JSON-RPC → response body is SSE text, parse `data:` lines

**Dependencies:** stdlib only (`urllib.request`, `json`, `uuid`). No `requests` needed.

**Future TypeScript need:** If the MCP server needs to do real-time hive proxying (Phase 5), a TypeScript port of this client will be needed in `mcp/cortex/src/hub-client.ts`. For Phase 3 (CLI commands), Python is sufficient.

---

## Phase 3: CLI Commands (`--hive-push` / `--hive-pull`)

**File:** `cortex/encoder/core.py`

### `--hive-push`

After vault scan + encoding, push all hive-eligible notes to the hub.

```python
def hive_push(notes, config):
    """Push eligible notes to hub memory."""
    client = HubClient(config["hive"]["hub_url"])
    client.connect()
    machine_id = config["hive"]["machine_id"]
    pushed = 0
    for note in notes:
        if not hive_eligible(note, config):
            continue
        key = f"vault/{machine_id}/{note.name}"
        value = json.dumps({
            "id": note.name,
            "type": note.note_type,
            "category": note.category,
            "tier": note.tier,
            "tags": note.tags,
            "aliases": note.aliases,
            "updated": note.updated,
            "content": note.clean_body(strip_links=True, drop_h1=True, drop_related=True),
            "machine_id": machine_id,
        })
        tags = ["vault", machine_id, note.tier]
        if note.note_type:
            tags.append(note.note_type)
        client.memory_set(key, value, tags)
        pushed += 1
    client.close()
    return pushed

def hive_eligible(note, config):
    """Check if a note should sync to hub."""
    if note.hive is True:
        return True
    if note.hive is False:
        return False
    replicate = config["hive"]["replicate_tiers"]
    for tier_pattern in replicate:
        if tier_pattern.endswith("*"):
            if note.tier.startswith(tier_pattern[:-1]):
                return True
        elif note.tier == tier_pattern:
            return True
    return False
```

### `--hive-pull`

Fetch vault notes from hub that are newer than local.

```python
def hive_pull(config):
    """Pull vault notes from hub. Newest timestamp wins."""
    client = HubClient(config["hive"]["hub_url"])
    client.connect()
    machine_id = config["hive"]["machine_id"]
    vault_root = Path(config["vault_path"])

    results = client.memory_search("vault/")
    if not isinstance(results, list):
        results = []
    pulled = 0
    for entry in results:
        note_data = json.loads(entry["value"])
        if note_data.get("machine_id") == machine_id:
            continue
        local_path = resolve_vault_path(vault_root, note_data)
        if local_path.exists():
            local_meta = parse_frontmatter(local_path)
            local_updated = local_meta.get("updated", "1970-01-01")
            if local_updated >= note_data["updated"]:
                continue
        write_hive_note(local_path, note_data)
        pulled += 1
    client.close()
    return pulled
```

### `--hive-status`

Check hub connection and vault sync state.

```python
def hive_status(config):
    """Check hub connection and vault sync state."""
    client = HubClient(config["hive"]["hub_url"])
    try:
        client.connect()
        connected = True
    except Exception:
        connected = False
    notes_synced = 0
    if connected:
        results = client.memory_search(f"vault/{config['hive']['machine_id']}/")
        notes_synced = len(results) if isinstance(results, list) else 0
    return {
        "connected": connected,
        "hub_url": config["hive"]["hub_url"],
        "machine_id": config["hive"]["machine_id"],
        "notes_synced": notes_synced,
        "replicate_tiers": config["hive"]["replicate_tiers"],
    }
```

### CLI integration

Add to `argparse` in `main()`:
```python
parser.add_argument("--hive-push", action="store_true", help="Push vault notes to hub")
parser.add_argument("--hive-pull", action="store_true", help="Pull vault notes from hub")
parser.add_argument("--hive-status", action="store_true", help="Show hive connection status")
```

---

## Phase 4: Hive Frontmatter

**File:** `cortex/encoder/core.py`

Add `hive` field to `VaultNote`:

```python
# In VaultNote.__init__:
self.hive = meta.get("hive", None)  # None = use tier default, True = force sync, False = never sync
```

Three-state logic:
- `None` → use `replicate_tiers` from config (default behavior)
- `True` → always sync to hub, even if tier is not in `replicate_tiers`
- `False` → never sync, even if tier is in `replicate_tiers`

**File:** `docs/VAULT_SCHEMA.md` — document the new field:
```yaml
---
id: my-note
type: knowledge
tier: core
hive: true          # optional: true (always sync), false (never sync), omit (use tier default)
---
```

---

## Phase 5: MCP Server Hive Proxy

**Files:** `mcp/cortex/src/index.ts`, `mcp/cortex/src/vault.ts`

### New env vars:
```
HIVE_ENABLED      → "false"
HIVE_HUB_URL      → "http://localhost:4096/mcp"
HIVE_MACHINE_ID   → (auto-generated UUID, persisted to _sync/machine-id)
```

### `memory_write` enhancement:
```typescript
// After writeNote() succeeds:
if (hiveEnabled && noteEligibleForHive(params, config)) {
    hubPushNote(params).catch(err =>
        log.warn("hive push failed, will retry on next encode", { error: err.message })
    );
}
```

Fire-and-forget. If the hub is unreachable, the note is still written locally and will sync on the next `--hive-push`.

### `memory_search` enhancement:
```typescript
const localResults = searchNotes(query, limit);

if (!hiveEnabled) return localResults;

const hubResults = await hubSearchNotes(query, limit);

// Merge: local wins on id collision, hub fills gaps
const merged = new Map<string, NoteSummary>();
for (const note of hubResults) {
    merged.set(note.id, note);
}
for (const note of localResults) {
    merged.set(note.id, note);  // local overwrites hub on collision
}
return Array.from(merged.values())
    .sort((a, b) => b.score - a.score)
    .slice(0, limit);
```

### Hub client in TypeScript:
For v1, use a lightweight inline HTTP call (~30 lines of fetch + SSE parse). A shared TypeScript client (`mcp/cortex/src/hub-client.ts`) should be extracted if real-time proxying becomes important. Note this as a TODO in the source.

### Auto-reload for hive notes:
Add a mtime check on a `hive-sync.json` file (written after each hub sync) alongside the existing `memory.json` mtime check. When `hive-sync.json` is newer, re-merge hub results on next `getIndex()`.

---

## Phase 6: Skill Commands

**File:** `skills/cortex-ai/SKILL.md`

### New commands:

| Command | What it does |
|---|---|
| `cortex hive status` | Show hub URL, machine ID, connected yes/no, last sync time, notes synced count, tier list |
| `cortex hive push` | Run `cortex encode --hive-push`, report count |
| `cortex hive pull` | Run `cortex encode --hive-pull`, report count |
| `cortex hive setup` | Interactive: prompt for hub_url, machine_id, replicate_tiers; write to cortex.yaml |

### `hive status` implementation:
```bash
cortex encode --show-config  # get hive fields
cortex encode --hive-status  # test hub connection, count vault/* keys
```

### `hive setup` implementation:
```python
def hive_setup_interactive(config_path):
    """Interactive first-time hive setup."""
    print("Cortex Hive Setup")
    print("=================")
    hub_url = input(f"Hub URL [{defaults['hub_url']}]: ").strip() or defaults["hub_url"]
    machine_id = input(f"Machine ID (e.g. office-desktop) [{defaults['machine_id']}]: ").strip()
    print("Replicate tiers (comma-separated, default: core,skill:*,project):")
    tiers_input = input("  > ").strip()
    replicate_tiers = [t.strip() for t in tiers_input.split(",")] if tiers_input else defaults["replicate_tiers"]
    # Write to cortex.yaml
    update_cortex_yaml(config_path, hub_url=hub_url, machine_id=machine_id, replicate_tiers=replicate_tiers)
```

---

## Phase 7: Bearer Token Auth (cortex-hub)

**After hive integration is shipped and working.**

### cortex-hub changes:

**File:** `cortex-hub/project/hub/mcp-server/src/index.ts`

Add Express middleware:
```typescript
const HUB_TOKEN = process.env.HUB_TOKEN;
if (HUB_TOKEN) {
    app.use("/mcp", (req, res, next) => {
        if (req.method === "DELETE") return next();
        const auth = req.headers.authorization;
        if (!auth || auth !== `Bearer ${HUB_TOKEN}`) {
            return res.status(401).json({ error: "Unauthorized" });
        }
        next();
    });
}
```

### cortex-ai changes:

**File:** `cortex.hub.client` — pass token in headers (already built into the client from Phase 2).

**File:** `cortex.yaml.example` — add `hub_token: ""` to hive block.

---

## Phase 8+: ROADMAP Items (parallel)

| Item | Where | What | Effort |
|---|---|---|---|
| `expires_at` frontmatter | `cortex/encoder/core.py` | Skip expired notes at encode + query time | Small |
| `agents:` routing | `cortex/encoder/core.py` | Per-target filtering by platform (field already parsed) | Small |
| `--graph` command | `cortex/encoder/core.py` | Parse `[[wiki-links]]` into edge list + visualization | Medium |
| Section-aware merge | `cortex/encoder/core.py` + `cortex.hub.client` | Replace timestamp-wins with per-section diff | Future |
| TypeScript hub client | `mcp/cortex/src/hub-client.ts` | Shared client for real-time MCP proxy | When needed |

---

## Dependency Graph

```
Phase 1 (config)
  └─► Phase 2 (hub client)
       ├─► Phase 3 (CLI commands)
       │    └─► Phase 6 (skill commands)
       └─► Phase 5 (MCP proxy)
            └─► Phase 6 (skill commands)

Phase 4 (frontmatter) ─── independent, can run parallel with 1-3

Phase 7 (auth) ─── independent, after phases 1-6 shipped

Phase 8+ (ROADMAP items) ─── independent, parallel with everything
```

---

## Version Impact

| Component | Change | Version bump |
|---|---|---|
| `SCHEMA_VERSION` | 1 → 2 | — |
| cortex-ai release | New feature (hive) | MINOR (1.3.0) |
| cortex-hub | No code changes for phases 1-6 | None |
| MCP server `package.json` | New env vars, no tool changes | PATCH |

---

## What's NOT changing

- **cortex-hub MCP server** — no new tools for v1. Existing `hub_memory_*` tools handle everything.
- **cortex-hub agent-sdk** — no changes. `HubClient` and `DaemonAgent` stay as-is.
- **cortex-hub setup** — no changes. The hub deployment process is unchanged.
- **cortex-ai single-machine mode** — fully preserved. Hive is opt-in via `hive.enabled: false`.

---

## Implementation Checklist

- [ ] Phase 1: Config + schema migration
  - [ ] Add `hive:` block to `cortex.yaml.example`
  - [ ] Parse `hive:` config in `cortex encode`
  - [ ] Add migration v1→v2 in `check_and_migrate()`
  - [ ] Bump `SCHEMA_VERSION` to 2
  - [ ] Add hive fields to `--show-config` output
- [ ] Phase 2: Python hub client
  - [ ] Create `cortex/hub/client.py`
  - [ ] Test against running cortex-hub
- [ ] Phase 3: CLI commands
  - [ ] Add `hive_eligible()` function
  - [ ] Add `--hive-push` command
  - [ ] Add `--hive-pull` command
  - [ ] Add `--hive-status` command
  - [ ] Add argparse entries
- [ ] Phase 4: Hive frontmatter
  - [ ] Add `hive` field to `VaultNote`
  - [ ] Update `docs/VAULT_SCHEMA.md`
- [ ] Phase 5: MCP server hive proxy
  - [ ] Add env var parsing
  - [ ] Add `memory_write` hive push
  - [ ] Add `memory_search` hub merge
  - [ ] Add `hive-sync.json` mtime check
- [ ] Phase 6: Skill commands
  - [ ] Add `cortex hive status` to SKILL.md
  - [ ] Add `cortex hive push` to SKILL.md
  - [ ] Add `cortex hive pull` to SKILL.md
  - [ ] Add `cortex hive setup` to SKILL.md
- [ ] Phase 7: Bearer token auth (after phases 1-6)
  - [ ] Add middleware to cortex-hub
  - [ ] Add `hub_token` to cortex-ai config
  - [ ] Pass token in `cortex.hub.client`
- [ ] Phase 8+: ROADMAP items
  - [ ] `expires_at` frontmatter
  - [ ] `agents:` routing
  - [ ] `--graph` command

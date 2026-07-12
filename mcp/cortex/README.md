# Cortex Memory MCP Server

The runtime query + capture layer for a Cortex vault. This is an
[MCP](https://modelcontextprotocol.io) server that exposes your distilled vault
to an agent as tools — so the agent can **read** memory mid-conversation and
**write** new memory back into the vault, closing the loop.

It complements `distill.py` (the build pipeline). Where the distiller turns your
vault into agent-consumable files, this server serves those files to the agent at
runtime and lets the agent add to them.

## The Two Loops

```
Build   (vault → agent):   author notes → distill.py → memory.json + core-context.md
Capture (agent → vault):   agent → memory_write → note written → distill.py (auto)
```

This server powers the runtime side of both: it reads `memory.json` for search,
and `memory_write` writes a note then triggers `distill.py` in the background so
the index stays current.

## Tools

| Tool | Kind | What it does |
|------|------|--------------|
| `memory_search` | read | Keyword search across all distilled notes; returns summaries |
| `memory_get` | read | Fetch one note by id (full content); falls back to the raw vault file if not yet distilled |
| `memory_related` | read | Find notes related by shared tags + category |
| `memory_write` | write | Create or update a note, then fire `distill.py` in the background |
| `memory_reload` | admin | Force-reload the index from `memory.json` (rarely needed — reads auto-reload on file change) |

### Auto-reload

Read tools check `memory.json`'s mtime on every call. When a background distill
(from `memory_write`, or a manual `distill.py` run) rewrites the file, the next
read transparently reloads — so the agent sees notes it wrote earlier in the same
session without restarting the server.

### memory_write

`memory_write` takes: `id`, `type`, `tier`, `category`, optional `phase`,
`aliases`, `tags`, `body`, and `update`. It resolves the correct vault directory
from `type` + `category` (+ `phase` for project entities), builds YAML
frontmatter, writes the `.md` file, and fires the distiller. With `update: true`
it patches an existing note's body and bumps its `updated` date while preserving
all other frontmatter.

The distiller runs **fire-and-forget** — the tool returns immediately and
`memory.json` catches up within ~1–2 seconds.

## Setup

The repo's top-level `./setup.sh` builds this server for you and prints
ready-to-paste config. To build it standalone:

```bash
cd mcp/cortex
npm install
npm run build
```

### Configure your agent

Point your MCP client at the built server with two required env vars:

| Env var | Required | Meaning |
|---------|----------|---------|
| `MEMORY_JSON` | yes | Path to the distilled `memory.json` |
| `VAULT_ROOT` | yes | Path to your Obsidian vault root |
| `DISTILL_SCRIPT` | no | Path to `distill.py` (default: `<VAULT_ROOT>/_sync/distill.py`) |
| `DISTILL_PYTHON` | no | Python interpreter for the distiller (default: `<VAULT_ROOT>/_sync/.venv/bin/python`, else `python3`) |

Example for **opencode** (`opencode.jsonc`):

```jsonc
"mcp": {
  "cortex": {
    "type": "local",
    "command": ["node", "/absolute/path/to/mcp/cortex/build/index.js"],
    "enabled": true,
    "environment": {
      "MEMORY_JSON": "/path/to/vault/_sync/distilled/memory.json",
      "VAULT_ROOT": "/path/to/vault"
    }
  }
}
```

Example for **Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "cortex": {
      "command": "node",
      "args": ["/absolute/path/to/mcp/cortex/build/index.js"],
      "env": {
        "MEMORY_JSON": "/path/to/vault/_sync/distilled/memory.json",
        "VAULT_ROOT": "/path/to/vault"
      }
    }
  }
}
```

## Making Capture Agent-Driven

The tools alone don't make the agent capture proactively — you also need a
standing instruction telling it *when* to write. The recommended pattern is a
`tier: core` note (e.g. `vault-capture-rules`) that distills into your always-on
context and defines the triggers and protocol:

1. **Search first** — `memory_search` to check for an existing note.
2. **Update if it exists** — `memory_write(..., update: true)`.
3. **Create if it doesn't** — `memory_write(...)`.

Triggers to encode: a stated/corrected preference → `feedback`; a non-obvious
solution → `knowledge`; a significant decision → `decision`; a project change →
`entity`; an explicit "remember this" → inferred; a handoff/compaction → a
`session` summary.

## Notes on Sharing

This directory is data-free: no vault contents, no credentials, no user-specific
paths. Everything vault-specific comes from the `MEMORY_JSON` / `VAULT_ROOT` env
vars at runtime. The `findVaultFile` / `resolveWritePath` directory maps assume
the conventional Cortex layout (`entities/`, `knowledge/`, `feedback/`,
`decisions/`, `logs/`) — adjust them in `src/vault.ts` if your vault differs.

## License

MIT.

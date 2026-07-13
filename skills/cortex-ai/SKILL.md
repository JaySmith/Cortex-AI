---
name: cortex-ai
description: Work with the Cortex vault — search notes, list by tier/type, add new notes, capture session knowledge, sync (capture-then-rebuild), import an existing agent, check the version or vault health, look up a note's vault path, or manage hive connection (shared vault across machines). Use when the user says "cortex", "search my notes", "add a note", "capture this", "cortex search", "cortex list", "cortex add", "cortex sync", "sync", "cortex get", "cortex open", "cortex import", "cortex version", "cortex status", "vault health", "update my memory", "cortex hive", "hive status", "hive push", "hive pull", or similar vault operations. On "sync", always capture session knowledge before rebuilding.
---

# Cortex AI

Persistent, tiered memory for AI agents. Notes live in an Obsidian-style vault and
are distilled into agent-consumable files; an MCP server serves them at runtime.

> **Paths.** `<CORTEX_HOME>` is the deployed Cortex runtime — the scripts agents
> actually run. Everything vault-related is resolved at runtime — never hard-code
> a vault path.
>
> - Cortex home (deployed runtime): `<CORTEX_HOME>`
> - Distiller: `<CORTEX_HOME>/distill.py`
> - VERSION file: `<CORTEX_HOME>/VERSION`
> - MCP server: `<CORTEX_HOME>/mcp/cortex/`
> - Config: `<CORTEX_HOME>/cortex.yaml` (co-located — no `--config` flag needed)
>
> **Interpreter.** Always invoke the Python scripts with plain `python3` — never
> the venv interpreter directly. `distill.py` and `gen-portfolio.py` self-bootstrap:
> they re-exec into the sibling `.venv` (which holds PyYAML) automatically, on
> macOS/Linux/Windows. If you see an `ERROR: PyYAML is required` message the venv is
> missing — create it with
> `python3 -m venv <CORTEX_HOME>/.venv && <CORTEX_HOME>/.venv/bin/pip install -r <CORTEX_HOME>/requirements.txt`.
> `cortex-import.py` and `cortex-uninstall.py` are stdlib-only and need no venv.
>
> **Resolving vault paths at runtime.** The `distill.py --show-config` command
> prints resolved paths as JSON. Run it and read the fields you need:
>
> ```bash
> python3 <CORTEX_HOME>/distill.py --show-config
> ```
>
> Returns: `cortex_version`, `config_file`, `vault_path`, `distill_py`,
> `core_context`, `memory_json`, `skills_dir`, `projects_dir`. Commands that touch
> the vault (`status`, `import`, `open`) read `vault_path` from here first.
> If the config isn't next to `distill.py`, pass it explicitly:
> `--show-config --config <vault>/_sync/cortex.yaml`.

**MCP tools (read):** `cortex_memory_search`, `cortex_memory_get`, `cortex_memory_related`
**MCP tools (write):** `cortex_memory_write` — creates/updates a note and auto-triggers distillation
**MCP tools (admin):** `cortex_memory_reload` — force-refresh the index (rarely needed; reads auto-reload on file change)

---

## Commands

### version

Report the Cortex **release version**, the **schema version**, and the MCP server
version. Cortex tracks two numbers with different jobs:

- **Release version** (SemVer, e.g. `1.0.0`) — the human-facing toolchain release.
  Lives in `VERSION`. See `CHANGELOG.md` for the MAJOR/MINOR/PATCH bump rules.
- **Schema version** (integer, e.g. `1`) — the on-disk data contract (memory.json
  shape, required frontmatter, cortex.yaml keys). Lives in `SCHEMA_VERSION`. This
  is the number upgrade-safety compares — not the SemVer.

1. **Release + schema** — read both plaintext files:
   ```bash
   cat <CORTEX_HOME>/VERSION <CORTEX_HOME>/SCHEMA_VERSION
   ```
2. **MCP server version** — read the `version` field from the server's package.json:
   ```bash
   grep '"version"' <CORTEX_HOME>/mcp/cortex/package.json
   ```
3. Report all, and flag a mismatch:
   ```
   Cortex release: <VERSION>   schema: <SCHEMA_VERSION>
   MCP server:     <package.json version>
   ```
   The MCP server also reads `VERSION` at startup, so its live `serverInfo.version`
   should match the release version. If the two files disagree, tell the user to
   rebuild the MCP server (`cd <CORTEX_HOME>/mcp/cortex && npm run build`).

Trigger phrases: "cortex version", "what version", "which version of cortex".

---

### status

Report vault **health and staleness** (distinct from `version`, which is just
version numbers). Gather:

1. **Resolved config** — run `distill.py --show-config`; note `cortex_version`,
   `schema_version`, `vault_schema_version`, `vault_path`, `config_file`,
   `memory_json`. If `schema_version` != `vault_schema_version`, a migration is
   pending (or the code is behind the vault). Run
   `distill.py --config <vault>/_sync/cortex.yaml --check` for a plain-language
   verdict and surface it.
2. **Last sync + staleness** — read `<vault>/_sync/last-sync.json` (`vault_path`
   from step 1). Compare its `timestamp` to now:
   - < 24h → OK
   - 24h–7d → warn ("last sync was N days ago")
   - > 7d → error ("stale — run `cortex sync`")
   If the file is missing, report "never synced".
3. **Vault vs distilled counts** — `last-sync.json` `note_count` is the vault
   total; the `_meta.count` in `memory_json` is the distilled (knowledge+entity)
   count. Report both, e.g. `42 notes in vault, 18 distilled to memory.json`.
4. **Frontmatter warnings** — run `distill.py --list`; flag notes shown as
   `untagged` (missing `tier`) or `type=unknown` (missing `type`).
5. **Skill-embed warnings** — a distill run prints
   `WARNING: skill dir missing, skipping: <dir>` for any `skill:<name>` note whose
   target dir doesn't exist. Run `distill.py --dry-run` and surface those lines.

Present as a short health block:
```
Cortex <release> (schema <n>) · vault: <path>
Schema: <in sync | MIGRATION PENDING v<a>->v<b> | ERROR vault newer>
Last sync: <relative time> [OK|WARN|STALE]
Notes: <vault total> in vault, <distilled> in memory.json
Warnings: <n> (or "none")
  - <note> missing tier
  - skill dir missing: <dir>
```

Trigger phrases: "cortex status", "vault health", "how is my vault".

---

### uninstall

Revert everything Cortex added and return the machine to its pre-Cortex state.
Your **vault notes are kept** — only Cortex's plumbing is removed (generated
`cortex.yaml`, the installed `cortex-ai` skill, and any agent config Cortex
rewrote such as `opencode.jsonc` instructions).

Always show the dry-run plan first, then apply only on confirmation:

```bash
VAULT=$(python3 <CORTEX_HOME>/distill.py --show-config | python3 -c 'import sys,json;print(json.load(sys.stdin)["vault_path"])')
# 1. Preview (changes nothing):
python3 <CORTEX_HOME>/cortex-uninstall.py --vault "$VAULT" --latest
# 2. Apply after the user confirms:
python3 <CORTEX_HOME>/cortex-uninstall.py --vault "$VAULT" --latest --apply
```

- `--latest` undoes the most recent install/import; omit it to undo **all**
  recorded manifests.
- `--backup <name>` targets one specific backup dir.
- `--purge` additionally deletes `_sync/distilled` (generated output) for a clean
  slate — notes are still kept.

After applying, remind the user to remove the MCP `cortex` entry from their agent
config and (optionally) delete the cloned repo.

Trigger phrases: "cortex uninstall", "remove cortex", "revert cortex",
"undo cortex", "get rid of cortex".

---

### search `<query>`

```
cortex_memory_search(query=<query>, limit=10)
```

Display: `id · type/category · alias · snippet`
If one clear match, offer to fetch the full note with `cortex_memory_get(id)`.

---

### get `<id>`

```
cortex_memory_get(id=<id>)
```

Returns full content + metadata. Falls back to raw vault file if not in memory.json.

---

### related `<id>`

```
cortex_memory_related(id=<id>)
```

---

### list `[filter]`

Run (add `--config <vault>/_sync/cortex.yaml` if the config isn't co-located with
`distill.py` — get the path from `--show-config`'s `config_file` field):
```bash
python3 <CORTEX_HOME>/distill.py --list
```

Filter output by the user's argument:
- `core` — only `tier=core` notes
- `project` — only `tier=project` notes
- `skill` / `skills` — only `tier=skill:*` notes
- `<type>` — filter by `type=<type>` (e.g. `knowledge`, `entity`, `feedback`)
- `all` or no argument — show everything

Group by tier, sorted alphabetically within each group.

**Note:** `--list` shows ALL vault notes (including vault-only, logs).
`cortex_memory_search` only searches distilled knowledge + entity notes in memory.json.

---

### add `<title>`

Create a new vault note. Steps:

1. **Ask type**: `["knowledge", "entity", "feedback", "decision", "log", "session"]`
2. **Ask tier** (suggest from type): `["core", "skill:<name>", "project", "vault-only"]`
3. **Ask category** (suggest from type):
   - knowledge → `patterns` · `api` · `calendars` · `infrastructure`
   - entity → `projects` · `people` · `systems` · `teams`
   - feedback → `preferences` · `workflow`
4. **Ask tags** (comma-separated, or skip).
5. Write with `cortex_memory_write` (id, type, tier, category, aliases, tags, body).
   It resolves the directory, writes the file, and triggers distillation
   automatically — no manual sync needed.
6. Print: `Note <created|updated>: <path>`

- `id` = slugified title (lowercase, hyphens)
- `aliases` = `["<title>"]`
- `updated` = today (`YYYY-MM-DD`)

---

### capture

Evaluate the recent conversation for capturable content and write it to the vault.
Follow the capture protocol from the `vault-capture-rules` core note:

1. For each capturable item, `cortex_memory_search` for an existing note.
2. `cortex_memory_write(..., update: true)` to patch, or `cortex_memory_write(...)` to create.
3. Report a one-line summary (id + created/updated).

Trigger phrases: "capture this", "distill that", "save what we decided",
"update your memory".

---

### import

Back up an existing agent's config and import it into the vault as `feedback`/`core`
notes tagged `review`. Reads AGENTS.md, CLAUDE.md, opencode `instructions[]`, and
`~/.claude/memory/*.md`. Backs up each source to `<vault>/_sync/backups/<ts>/`.

First resolve the vault path:
```bash
VAULT=$(python3 <CORTEX_HOME>/distill.py --show-config | python3 -c 'import sys,json;print(json.load(sys.stdin)["vault_path"])')
# Preview first
python3 <CORTEX_HOME>/cortex-import.py --vault "$VAULT" --dry-run
# Then import
python3 <CORTEX_HOME>/cortex-import.py --vault "$VAULT"
```

After import: review notes tagged `review` in `<vault>/feedback/`, adjust
`type`/`tier`, then run `cortex sync`.

---

### sync

A sync is **capture-then-rebuild**, not just a rebuild. "Sync" is the moment to
reconcile everything worth remembering from the current session into the vault
*before* regenerating distilled outputs — otherwise the rebuild just re-emits
stale knowledge and the session's lessons are lost.

**Always run these two steps in order:**

1. **Capture first.** Run the `capture` command reflex (see above): scan the
   session against the `vault-capture-rules` triggers (preferences/corrections,
   non-obvious knowledge, decisions, project changes, "remember this", handoffs)
   and `cortex_memory_write` each capturable item (search → update-or-create).
   If nothing meaningful happened this session, say so and skip. Do **not** skip
   this step silently — a bare distiller run is not a sync.

2. **Then rebuild.**
   ```bash
   python3 <CORTEX_HOME>/distill.py
   ```
   (Add `--config <vault>/_sync/cortex.yaml` if the config isn't next to
   `distill.py`.) Print the full output. Confirm success on completion.

Report both halves: what was captured (ids + created/updated), then the distill
result. Individual `cortex_memory_write` calls already trigger distillation, so
step 2 is mainly for bulk rebuilds after many manual edits — but step 1 is the
point of a sync.

Trigger phrases: "sync", "cortex sync", "sync my vault".

---

### portfolio `[--no-jira]`

```bash
python3 <CORTEX_HOME>/gen-portfolio.py [--no-jira]
```

Pass `--no-jira` for vault-only (faster, no network calls).

---

### open `<id>`

Resolve the vault file path by checking these directories in order (matching
`findVaultFile` logic), relative to the vault root (get it from
`distill.py --show-config` → `vault_path`):

```
entities/projects/delivery/<id>.md
entities/projects/completed/<id>.md
entities/projects/discovery/<id>.md
entities/projects/<id>.md
entities/people/<id>.md
entities/systems/<id>.md
entities/teams/<id>.md
knowledge/api/<id>.md
knowledge/patterns/<id>.md
knowledge/infrastructure/<id>.md
knowledge/calendars/<id>.md
feedback/<id>.md
decisions/<id>.md
logs/<id>.md
```

Print the resolved path: `Vault file: <path>`. If not found, suggest `cortex list`.

---

### hive `status` / `push` / `pull` / `setup`

Manage connection to a cortex-hub instance for shared vault access across machines.

**hive status**
```bash
python3 <CORTEX_HOME>/distill.py --hive-status
```
Prints: connected yes/no, hub URL, machine ID, notes synced, replicate tiers.

**hive push**
```bash
python3 <CORTEX_HOME>/distill.py --hive-push
```
Pushes all hive-eligible notes to the hub. Reports count pushed.

**hive pull**
```bash
python3 <CORTEX_HOME>/distill.py --hive-pull
```
Pulls vault notes from hub that are newer than local. Newest `updated` timestamp wins.

**hive setup**
Interactive first-time setup. Prompt the user for:
1. **Hub URL** (default: `http://localhost:4096/mcp`)
2. **Machine ID** (e.g. `office-desktop`, `laptop`) — unique name for this machine
3. **Replicate tiers** (default: `core, skill:*, project`)

Write the `hive:` block to `<vault>/_sync/cortex.yaml`. If the block already exists,
confirm before overwriting.

After setup, suggest running `cortex hive status` to verify the connection.

Trigger phrases: "cortex hive", "hive status", "hive push", "hive pull",
"setup hive", "connect to hub".

---

## Tier Guide

| tier | when to use |
|------|-------------|
| `core` | Standing preferences, persona, default behaviours — always loaded |
| `skill:<name>` | Heavy knowledge needed only when a specific skill loads |
| `project` | Project context (goals, roadmap, phase) |
| `vault-only` | Research, drafts, session notes — never distilled to agents |

---

## After Adding Notes

`cortex_memory_write` triggers distillation automatically in the background, so
`memory.json` and the distilled outputs update within ~1-2 seconds. The MCP server
auto-reloads its index whenever `memory.json` changes on disk, so reads see notes
written earlier in the same session without any extra step. Use
`cortex_memory_reload` only to force an immediate refresh.

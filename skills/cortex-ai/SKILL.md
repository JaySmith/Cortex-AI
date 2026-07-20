---
name: cortex-ai
description: Work with the Cortex vault — search notes, list by tier/type, add new notes, capture session knowledge, sync (capture-then-rebuild), import an existing agent, check the version or vault health, look up a note's vault path, or manage hive connection (shared vault across machines). Use when the user says "cortex", "search my notes", "add a note", "capture this", "cortex search", "cortex list", "cortex add", "cortex sync", "sync", "cortex get", "cortex open", "cortex import", "cortex version", "cortex status", "vault health", "update my memory", "cortex hive", "hive status", "hive push", "hive pull", or similar vault operations. For "auto-learn", "what did you learn?", "what should I capture?", "learning mode", or "learning check", load the auto-learn skill instead. On "sync", always capture session knowledge before rebuilding.
---

# Cortex AI

Persistent, tiered memory for AI agents. Notes live in an Obsidian-style vault
and are encoded into agent-consumable files. The `cortex` CLI provides search,
read, and write access.

> **Paths.** Resolve vault paths at runtime: `cortex encode --show-config`
> (returns JSON with `vault_path`, `config_file`, `memory_json`, etc.).

**CLI commands (read):** `cortex memory search`, `cortex memory get`
**CLI commands (write):** `cortex memory write` — creates/updates a note and auto-triggers encoding

---

## Core Commands

### search `<query>`

```
cortex memory search "<query>"
```

Display: `id · type/category · alias · snippet`
If one clear match, offer to fetch the full note with `cortex memory get <id>`.

### get `<id>`

```
cortex memory get <id>
```

Returns full content + metadata. Falls back to raw vault file if not in memory.json.

### add `<title>`

Create a new vault note:

1. **Ask type**: `["knowledge", "entity", "feedback", "decision", "log", "session"]`
2. **Ask tier** (suggest from type): `["core", "skill:<name>", "project", "vault-only"]`
3. **Ask category** (suggest from type):
   - knowledge → `patterns` · `api` · `calendars` · `infrastructure`
   - entity → `projects` · `people` · `systems` · `teams`
   - feedback → `preferences` · `workflow`
4. **Ask tags** (comma-separated, or skip).
5. Write with `cortex memory write --title "..." --type ... --tier ... --body "..."`.
6. Print: `Note <created|updated>: <path>`

- `id` = slugified title (lowercase, hyphens)
- `aliases` = `["<title>"]`
- `updated` = today (`YYYY-MM-DD`)

To patch an existing note, add `--update`:
```
cortex memory write --title "..." --type ... --tier ... --body "..." --update
```

### capture

Evaluate the recent conversation for capturable content and write it to the vault:

1. For each capturable item, `cortex memory search` for an existing note.
2. `cortex memory write ... --body "..."` to create, or add `--update` to patch.
3. Report a one-line summary (id + created/updated).

Trigger phrases: "capture this", "encode that", "save what we decided", "update your memory".

### sync

A sync is **capture-then-rebuild-then-drain**, in this order:

1. **Capture first.** Scan the session for capturable content (preferences, corrections,
   non-obvious knowledge, decisions, project changes) and `cortex memory write` each item.
   If nothing meaningful happened, say so and skip. Do **not** skip silently.

2. **Then rebuild.**
   ```bash
   cortex encode
   ```

3. **Then drain spent session artifacts.** For each `log`/`session` note written *before
   this session*, patch `drained: true` via `cortex memory write ... --update`.
   Never drain notes written in the current session. Then purge:
   ```bash
   cortex encode --purge-apply
   ```

Trigger phrases: "sync", "cortex sync", "sync my vault".

**Optional: auto-learn step.** After drain, if the session produced substantive
content (>5 meaningful turns), optionally run the `auto-learn` skill's observe
→ propose cycle. The human decides what gets captured. Do not auto-write.

> **For full details** on sync drain guardrails, protected notes, and all advanced
> commands (version, status, uninstall, list, import, purge, portfolio, open, hive),
> read `reference.md` in this skill directory.

---

## Tier Guide

| tier | when to use |
|------|-------------|
| `core` | Standing preferences, persona, default behaviours — always loaded |
| `skill:<name>` | Heavy knowledge needed only when a specific skill loads |
| `project` | Project context (goals, roadmap, phase) |
| `vault-only` | Research, drafts, session notes — never encoded to agents |

---

`cortex memory write` triggers encoding automatically in the background
(unless `--no-encode` is passed). The CLI re-reads `memory.json` fresh on
every call, so no manual reload is needed.

# cortex-ai — Operations Reference

Detail for the heavy `cortex-ai` commands. Loaded on demand when a command runs.
`SKILL.md` holds paths, interpreter rules, MCP tool names, and the lightweight
read commands (search, get, related, list).

> Paths and the `--show-config` runtime resolution pattern live in `SKILL.md` —
> this file assumes them. Never hard-code a vault path.

---

## version

Report the Cortex **release version**, the **schema version**, and the MCP server
version. Cortex tracks two numbers with different jobs:

- **Release version** (SemVer, e.g. `1.0.0`) — the human-facing toolchain release.
  Reported by `cortex version` as `Cortex:  <version>`. See `CHANGELOG.md` for the
  MAJOR/MINOR/PATCH bump rules.
- **Schema version** (integer, e.g. `1`) — the on-disk data contract (memory.json
  shape, required frontmatter, cortex.yaml keys). Reported by `cortex version` as
  `Schema:  <n>`. This is the number upgrade-safety compares — not the SemVer.

1. **Release + schema** — read both from `cortex version`:
   ```bash
   cortex version
   ```
   It prints `Cortex:  1.4.0` (release) and `Schema:  2` (schema).
2. **MCP server version** — read the `version` field from the server's package.json:
   ```bash
   grep '"version"' /Users/smithjay/.config/opencode/mcp/cortex/package.json
   ```
3. Report all, and flag a mismatch:
   ```
   Cortex release: <version>   schema: <n>
   MCP server:     <package.json version>
   ```
   The MCP server's live `serverInfo.version` should match the release version
   from `cortex version`. If the two disagree, tell the user to
   rebuild the MCP server (`cd /Users/smithjay/.config/opencode/mcp/cortex && npm run build`).

Trigger phrases: "cortex version", "what version", "which version of cortex".

---

## status

Report vault **health and staleness** (distinct from `version`, which is just
version numbers). The `cortex status` command prints a health summary directly;
use the steps below to gather richer detail. Gather:

1. **Resolved config** — run `cortex encode --show-config`; note `cortex_version`,
   `schema_version`, `vault_schema_version`, `vault_path`, `config_file`,
   `memory_json`. If `schema_version` != `vault_schema_version`, a migration is
   pending (or the code is behind the vault). Run
   `cortex encode --check` for a plain-language
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
4. **Frontmatter warnings** — run `cortex encode --list`; flag notes shown as
   `untagged` (missing `tier`) or `type=unknown` (missing `type`).
5. **Skill-embed warnings** — a distill run prints
   `WARNING: skill dir missing, skipping: <dir>` for any `skill:<name>` note whose
   target dir doesn't exist. Run `cortex encode --dry-run` and surface those lines.

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

## uninstall

Revert everything Cortex added and return the machine to its pre-Cortex state.
Your **vault notes are kept** — only Cortex's plumbing is removed (generated
`cortex.yaml`, the installed `cortex-ai` skill, and any agent config Cortex
rewrote such as `opencode.jsonc` instructions).

Always show the dry-run plan first, then apply only on confirmation:

```bash
# 1. Preview (changes nothing):
cortex uninstall
# 2. Apply after the user confirms:
cortex uninstall --apply
```

`cortex uninstall` auto-detects the vault. These flags pass through to
`cortex uninstall`:

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

## add `<title>`

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

**Output shape:** one line — `Note created: <path>` or `Note updated: <path>`.

---

## capture

Evaluate the recent conversation for capturable content and write it to the vault.

**Capture events** (inlined from the `vault-capture-rules` core note so this command
is self-contained). Capture when the session **changes one of the five things worth
remembering**:

| Event | Capture when… | Type |
|-------|---------------|------|
| **Goal** | What we're trying to achieve changed or was clarified | `entity` |
| **Plan/State** | How we'll get there, or the current status of work, changed | `entity` |
| **Knowledge** | Something non-obvious was worked out | `knowledge` |
| **Risk** | Something that might prevent success was identified | `risk` |
| **Decision** | A commitment was made (with reasoning) | `decision` |

Plus two capture *sources*: a **preference/correction** the user states →
`feedback`/`core`; and an explicit **"remember this"** → capture as the fitting type.

### The meaningful bar

> Canonical definition lives in the `vault-capture-rules` core note (loaded every
> session). Mirrored here so the skill is self-contained; keep the two in sync.

An event firing is necessary but not sufficient. Capture only what is **durable** —
useful to a *future* session, not just this one. Tiebreaker for borderline items:

> **Ask: "If a fresh agent started cold next week, would *not* having this note make
> it repeat work, break a stated preference, or lose important context?"**
> **Yes →** capture. **No →** skip. **Unsure →** capture as `tier: vault-only`
> (cheap, non-distilled, prunable later).

**Disqualifiers — never capture, even if an item superficially matches an event:**

- **Pure Q&A** — user asked, you answered, nothing changed.
- **Restatement** — the item already exists as a note. Always `cortex_memory_search`
  first; if the write would be a no-op, skip.
- **Scratch / transient** — command output, file paths, in-progress debugging with no
  conclusion reached.
- **Speculation** — "we might…", "maybe later…". Capture decisions and risks, not musings.
- **Self-evident** — behaviour the agent already does by default.

So "something meaningful happened" (the session-note trigger) resolves to: **at least
one of the five events produced a durable, non-disqualified item.** A handoff with
only Q&A and scratch work behind it is *not* meaningful — skip the session note.

`risk` is a first-class type: tier it `project` when it threatens a specific project,
`core` for a standing risk. Risk notes are searchable via `cortex_memory_search`.

Protocol (always three steps):

1. For each capturable item, `cortex_memory_search` for an existing note.
2. `cortex_memory_write(..., update: true)` to patch, or `cortex_memory_write(...)` to create.
3. Report a one-line summary (id + created/updated).

**Output shape:** one line per note — `<id> [created|updated]`. If no triggers
fired, report `Nothing capturable found` explicitly (do not stay silent).

Trigger phrases: "capture this", "distill that", "save what we decided",
"update your memory".

---

## import

Back up an existing agent's config and import it into the vault as `feedback`/`core`
notes tagged `review`. Reads AGENTS.md, CLAUDE.md, opencode `instructions[]`, and
`~/.claude/memory/*.md`. Backs up each source to `<vault>/_sync/backups/<ts>/`.

```bash
# Preview first
cortex import --dry-run
# Then import
cortex import
```

**Note:** `cortex import` auto-detects the vault. Verify it resolves to your real
vault (`cortex status` shows the vault path) before running — if notes land in the
wrong directory, move them into `<vault>/feedback/` and re-encode.

After import: review notes tagged `review` in `<vault>/feedback/`, adjust
`type`/`tier`, then run `cortex sync`.

---

## sync

A sync is **capture-then-rebuild-then-drain**, not just a rebuild. "Sync" is the
moment to reconcile everything worth remembering from the current session into the
vault *before* regenerating distilled outputs — otherwise the rebuild just re-emits
stale knowledge and the session's lessons are lost. Once the lessons are safely
distilled, the spent session artifacts are drained and purged.

**Always run these three steps in order:**

1. **Capture first.** Scan the session for the **five capture events** (defined under
   `capture` above) and `cortex_memory_write` each item (search → update-or-create):

   | Event | Type | | Event | Type |
   |-------|------|-|-------|------|
   | Goal | `entity` | | Risk | `risk` |
   | Plan/State | `entity` | | Decision | `decision` |
   | Knowledge | `knowledge` | | + preference → `feedback`, "remember this" → fitting type |  |

   Apply **the meaningful bar** (defined under `capture` above): capture only durable
   items — those a fresh agent would suffer for lacking next week — and skip the
   disqualifiers (pure Q&A, restatement, scratch, speculation, self-evident). When
   unsure, capture as `vault-only`.

   If nothing meaningful happened this session, say so and skip. Do **not** skip
   this step silently — a bare distiller run is not a sync. **If a
   `cortex_memory_write` fails, stop — do not proceed to rebuild.** Surface the
   error and ask the user to resolve it (a rebuild over a half-captured session
   loses the uncaptured lessons).

2. **Then rebuild.**
   ```bash
   cortex encode
   ```
   (Add `--config <vault>/_sync/cortex.yaml` to target a specific vault;
   auto-detected by default.) Print the full output.

3. **Then drain spent session artifacts.** Once step 1 has extracted every durable
   lesson into knowledge/entity notes, the raw `log` and `session` files from
   **prior** sessions are dead weight. Mark them drained and purge them:

   a. For each `log`/`session` note written *before this session*, patch its
      frontmatter with `drained: true` via
      `cortex_memory_write(id, ..., update: true)`. **Never** drain a note you
      wrote in the current session — its lessons may not be captured yet.

   b. **Protected notes — never drain these** (ongoing logs, not one-shot session
      artifacts):
      - `hardware-incidents` — a running incident log, appended over time.
      - Any note whose id does **not** start with a `YYYY-MM-DD-` date prefix is
        presumed an ongoing log; leave it unless the user says otherwise.

   c. Purge the flagged files (preview first, then apply):
      ```bash
      cortex encode --purge        # preview
      cortex encode --purge-apply  # delete + rebuild
      ```
      `--purge-apply` deletes the drained files and rebuilds distilled outputs in
      one pass.

Report all three parts: what was captured (ids + created/updated), the distill
result, and what was drained/purged (ids). Individual `cortex_memory_write` calls
already trigger distillation, so step 2 is mainly for bulk rebuilds after many
manual edits — but step 1 is the point of a sync, and step 3 keeps the vault free
of spent session logs.

Trigger phrases: "sync", "cortex sync", "sync my vault".

---

## purge `[--apply]`

Delete spent session artifacts — `log` and `session` notes flagged
`drained: true` in their frontmatter. A drained note has already had its durable
lessons extracted into knowledge/entity notes (that's what the sync capture step
does), so the raw file is dead weight.

Preview first, then apply on confirmation:
```bash
cortex encode --purge        # list candidates
cortex encode --purge-apply  # delete + rebuild
```

- Only touches types `log` and `session`, and only when `drained: true` is set.
- `--purge-apply` deletes the files and rebuilds distilled outputs in one pass.
- **Protected:** `hardware-incidents` and any non-date-prefixed id are ongoing
  logs — never flag them drained (see the `sync` step-3 guardrails).

Normally you don't invoke this directly — `cortex sync` runs the drain step
automatically. Use it standalone to clean up after manual `drained: true` edits.

Trigger phrases: "cortex purge", "purge drained logs", "clean up logs".

---

## portfolio `[--no-jira]`

> **Not yet exposed in the `cortex` CLI (v1.4.0).** There is no `cortex portfolio`
> command or `cortex encode --portfolio` flag. If a portfolio generator is needed,
> confirm the current entry point with `cortex --help` before use; do not invent a
> flag. `--no-jira` (vault-only, no network calls) was the historical option.

---

## open `<id>`

Resolve the vault file path by checking these directories in order (matching
`findVaultFile` logic), relative to the vault root (get it from
`cortex encode --show-config` → `vault_path`):

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

## hive `status` / `push` / `pull` / `setup`

Manage connection to a cortex-hub instance for shared vault access across machines.

**hive status**
```bash
cortex encode --hive-status
```
Prints: connected yes/no, hub URL, machine ID, notes synced, replicate tiers.

**hive push**
```bash
cortex encode --hive-push
```
Pushes all hive-eligible notes to the hub. Reports count pushed.

**hive pull**
```bash
cortex encode --hive-pull
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

---

## Known Failures

| Scenario | Response |
|----------|----------|
| `ERROR: PyYAML is required` | The Cortex CLI venv is broken. Reinstall/upgrade with `cortex install` (or `cortex bootstrap`). Verify with `cortex doctor`. |
| Vault path unresolvable (`cortex encode --show-config` errors or empty `vault_path`) | Do not proceed. Check `cortex.yaml` exists at `/Users/smithjay/cortex-ai/_sync/cortex.yaml`; if not, pass `--config` explicitly. Tell the user rather than guessing a path. |
| `cortex_memory_write` fails mid-capture | Stop. Do **not** run the rebuild step — a rebuild over a half-captured session loses uncaptured lessons. Surface the error and ask the user to resolve. |
| Schema version mismatch (`schema_version` != `vault_schema_version`) | Run `cortex encode --check` for the verdict. Do not rebuild until migration is resolved. |
| Skill dir missing during distill (`WARNING: skill dir missing`) | Surface the warning line. Either create the target skill dir or remove the `skill:<name>` tier tag from the offending note. |
| MCP server version != release version | Rebuild: `cd /Users/smithjay/.config/opencode/mcp/cortex && npm run build`. |
| `cortex encode` crashes (Python traceback) | Show full stderr. Run `cortex doctor` to validate the installation; reinstall with `cortex install` if the CLI itself is broken. |

---

## Testing

Re-run when the skill, the Cortex runtime, or the MCP server changes. Verification
is manual against the live vault.

| Test | How | Pass criterion |
|------|-----|----------------|
| Trigger | Prompt "cortex search X", "add a note", "cortex status" | Skill selected |
| Paraphrase | Reword ("find in my notes", "save this to the vault", "how's my vault") | Still selected |
| Negative trigger | "sync my git repo", "search the codebase", "what Node version" | **Not** selected |
| Functional — search | `cortex_memory_search` on a known term | Returns matching notes, formatted `id · type/category · alias · snippet` |
| Functional — add | `add` a test note, then `get` it | Note exists at reported path with correct tier/type |
| Functional — status | Run `status` | Health block renders; staleness verdict correct vs last-sync.json |
| Functional — sync | Run `sync` with a capturable item present | Capture → rebuild → drain all run; three-part report produced |
| Edge — nothing to capture | Run `sync` after trivial Q&A | Explicitly reports "nothing capturable", skips silently-skip trap |
| Edge — drain protection | Run `sync` with `hardware-incidents` present | It is **not** drained |
| Edge — write failure | Simulate a failing `cortex_memory_write` during sync | Rebuild is **not** run; error surfaced |
| Repeatability | Run `status` twice with no changes | Identical health block |

---

## Success Metrics

Track informally to know if the skill is healthy:

- **Capture completeness** — durable lessons that made it into the vault vs those
  lost to a skipped/failed capture. Target: high. If durable items are being missed,
  the meaningful-bar disqualifiers are too aggressive; if noise is accumulating,
  they're too loose.
- **Sync integrity** — syncs that completed all three steps (capture, rebuild,
  drain) without a half-run. Target: 100%.
- **Vault staleness** — time since last sync (from `status`). Target: < 24h during
  active work.
- **False-drain rate** — protected/ongoing notes accidentally drained. Target:
  zero; nonzero means the drain guardrails need sharpening.

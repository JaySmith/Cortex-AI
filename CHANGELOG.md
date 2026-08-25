# Changelog

All notable changes to Cortex are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and the project follows the
versioning strategy described below.

## Versioning strategy

Cortex tracks **two independent numbers**:

| Number | File | Meaning | Consumers |
|--------|------|---------|-----------|
| **Release version** (SemVer, e.g. `1.0.0`) | `VERSION` | Which release of the Cortex toolchain this is | humans, changelog, `--version`, MCP `serverInfo.version`, `package.json` |
| **Schema version** (integer, e.g. `1`) | `SCHEMA_VERSION` | The on-disk data contract (memory.json shape, required frontmatter, `cortex.yaml` keys, encoded layout) | upgrade-safety checks and migrations only |

The two are decoupled on purpose: a PATCH release can never silently break your
data, and a MAJOR release does not have to bump the schema.

### When to bump the release version (SemVer)

- **MAJOR** (`2.0.0`) — a breaking change for existing users: removing/renaming a
  `cortex.yaml` key, a CLI flag; a surprising change to default
  behaviour; or a schema bump with **no** automatic migration.
- **MINOR** (`1.1.0`) — a backward-compatible feature: new CLI flag, new CLI command,
  new config key with a safe default; or a schema bump that ships an **automatic**
  migration.
- **PATCH** (`1.0.1`) — a bug fix, doc fix, or internal refactor with no
  user-visible change and no schema change.

Rule of thumb: if a user must *do* something after upgrading, it is at least MINOR
and needs a changelog entry. If their vault could be *misread*, it is MAJOR.

### Release discipline (bump at release time, not later)

Versioning only works if the bump happens *with* the change, not in a batch
afterward. Loose `feat:` / user-visible commits piling up on a released version is
a bug — the version stops describing what's shipped.

**Rule:** every commit that qualifies as MINOR or MAJOR (a new tool/flag/MCP tool,
or a change to existing behavior a user relies on) must, before the work is
considered done, either:

1. bump `VERSION` (and `SCHEMA_VERSION` if the data contract changed) **in the same
   commit** with a matching `## [Unreleased]` → `[x.y.z]` CHANGELOG entry; **or**
2. be immediately followed by a `chore: release x.y.z` commit that bumps `VERSION`,
   dates the CHANGELOG section, and rebuilds the MCP (the `prebuild` hook syncs
   `package.json`).

PATCH-only changes (bug/doc/refactor, no user-visible effect) may accumulate under
`[Unreleased]` and ship with the next MINOR/MAJOR.

**Checklist for a release commit:**
- [ ] `VERSION` bumped (and `SCHEMA_VERSION` if schema changed)
- [ ] CHANGELOG `[Unreleased]` promoted to `[x.y.z] — YYYY-MM-DD`
- [ ] live install redeployed (`cortex install --upgrade`) and agent restarted

### When to bump the schema version

Increment `SCHEMA_VERSION` by **+1** whenever the on-disk contract changes, and add
a migration entry in `cortex/encoder/core.py`'s `MIGRATIONS` registry for the new
step. Migrations must be idempotent and only touch `_sync/` contents — never user
notes.

### Upgrading safely

`cortex encode` compares the code's `SCHEMA_VERSION` against the `schema_version`
stamped in the vault's `memory.json` on every run:

- **equal / fresh vault** → proceed.
- **code newer** → auto-back up `_sync/`, run registered migrations, then proceed.
- **code older than vault** → refuse to run (no silent downgrade).

Check status any time with:

```bash
cortex encode --config <vault>/_sync/cortex.yaml --check
```

### Reverting Cortex

`cortex install` writes install manifests to
`<vault>/_sync/backups/`. `cortex uninstall` reads them to restore modified
files and delete created ones, returning the machine to its pre-Cortex state.
Your vault notes are always kept.

```bash
cortex uninstall --vault <vault> --latest          # preview
cortex uninstall --vault <vault> --latest --apply  # revert
```

---

## [Unreleased]

## [2.0.1] — 2026-08-25

### Fixed
- `cortex lint --vault PATH` no longer requires `_sync/cortex.yaml`. An explicit
  `--vault` is now trusted if it is a real directory, so lint works on a fresh or
  example vault (the `cortex.yaml` gate is kept only for auto-detection). Fixes a
  long-standing `test_lint_clean_vault` failure.
- `cortex upgrade` no longer prints the false "automated migration is not
  supported" warning on the schema-changed path. It now states accurately that
  migration runs during the re-encode step (which backs up `_sync/` first).
- `test_skips_underscore_dirs` failed on a fresh checkout because
  `example-vault/` now ships a `_sync/` dir; the test's `mkdir` now passes
  `exist_ok=True`.

### Added
- `requirements-dev.txt` declaring `pytest` (previously undeclared — had to be
  installed by hand to run the suite). See `docs/DEVELOPMENT.md` → Running the tests.

### Documentation
- Documented `cortex doctor` in the troubleshooting guide (core + per-platform
  checks, symbol legend, and how it differs from `status` / `encode --check`).
- Expanded the vault-schema wiki-links section to cover link **resolution** (id →
  alias → case-insensitive fallback, dangling detection, `--graph`, the
  `dangling-wiki-link` lint rule), not just stripping.

## [2.0.0] — 2026-07-20

### Breaking
- **MCP server removed** (`mcp/cortex/`). All memory operations migrated to CLI
  commands. The `cortex` Typer app is now the sole entry point. Agents that
  previously used `cortex_memory_*` MCP tools must switch to `cortex memory *`
  CLI commands. See `docs/cli-reference.md` for the full command reference.
- **`cortex sync` replaced by individual `cortex memory *` commands.** The old
  sync-then-encode loop is now explicit: `cortex memory write` → auto-encode.

### Added
- **`cortex memory get <id>`** — fetch a single note by id (memory.json first,
  then vault file fallback).
- **`cortex memory list`** — table of all notes with `--tier`/`--type` filters.
- **`cortex memory write`** — create or update notes with auto-encode trigger.
- **`cortex memory search <query>`** — keyword search across memory.json.
- **`cortex lint`** — vault linting with 11 rules across three severity levels.
  Supports `--strict`, `--fix`, `--note <id>`, `--json`, `--rules`.
- **`cortex.vault` subpackage** — shared link parsing primitives
  (`extract_wiki_links`, `strip_wiki_links`, `resolve_wiki_links`) used by
  both the encoder and the lint command.
- **`scan_vault(require_type=False)`** parameter for linting untyped notes.
- **16 tests for CLI memory commands** in `tests/test_memory_cli.py`.
- **21 tests for cortex lint** in `tests/test_lint.py`.

### Changed
- `build_wiki_graph` now delegates link resolution to
  `cortex.vault.links.resolve_wiki_links`, removing ~25 lines of duplicate logic.
- `scan_vault` duplicate warnings now write to stderr instead of stdout.
- `cortex import` uses `_find_vault()` (shared helper) instead of its own inline
  hardcoded-path detection, fixing a bug where non-`~/Cortex` vaults were missed.

### Fixed
- `cortex import` no longer silently writes to the wrong directory when the vault
  is named something other than `Cortex` (e.g. `cortex-ai`). Now errors with a
  clear message if no vault is found.

## [1.4.0] — 2026-07-13

### Added
- **`risk` note type is now first-class in the MCP tool and vault layout.** The
  capture rules already described `risk` as a first-class type and `cortex.yaml`
  already indexed it (`include_types`), but the `memory_write` MCP tool rejected
  it and `resolveWritePath` had no home for it. Added `"risk"` to the tool's type
  enum and description, gave it its own `risks/` directory (parallel to
  `decisions/`), and taught `findVaultFile` to look there. Risk notes now write
  correctly and are searchable. Additive — no schema bump.

## [1.3.0] — 2026-07-13

### Added
- **Purge for spent session artifacts.** New `distill.py --purge` (preview) and
  `--purge-apply` (delete + rebuild) flags remove `log` and `session` notes flagged
  `drained: true` in frontmatter. A drained note has already had its durable
  lessons extracted into knowledge/entity notes, so the raw file is dead weight.
  Only ever touches types `log`/`session`, and only when `drained: true` is
  explicitly set — no other note is at risk. `VaultNote` gained a `drained`
  attribute; the field is additive and ignored by every distillation target, so no
  schema bump is needed.

### Changed
- **`cortex sync` is now capture-then-rebuild-then-drain.** After capture and
  rebuild, the sync step marks prior-session `log`/`session` notes `drained: true`
  and runs `--purge-apply`, keeping the vault free of spent session logs. Ongoing
  logs (`hardware-incidents`, any non-date-prefixed id) are protected and never
  drained. Added a standalone `purge` command to the `cortex-ai` skill.

### Docs
- Added `roadmap.md` — planned direction for future releases (Cortex Hive remote
  vault federation, cross-platform parity, someday vector retrieval). Linked from
  the README repo-layout and Docs sections.

## [1.2.2] — 2026-07-11

### Fixed
- **`distill.py` and `gen-portfolio.py` self-bootstrap into `.venv`.** Both scripts
  require PyYAML, which lives only in the sibling `.venv` — never in the macOS
  Homebrew system Python (externally-managed, can't `pip install`). A venv re-exec
  guard at the top of each script detects the sibling `.venv` and `os.execv`s into
  it before any third-party import, so `python3 <script>` now works correctly from
  any interpreter on macOS/Linux/Windows. Previously a bare `python3` invocation
  produced `ERROR: PyYAML is required` every session. The guard detects "already in
  the venv" via `sys.prefix` (not `sys.executable`): the venv's `bin/python` is
  usually a symlink to the same real interpreter as system Python, so an
  `sys.executable` comparison would falsely match and skip the re-exec. If no venv
  exists the guard falls through and the existing `ImportError` fires as before.
  `cortex-import.py` / `cortex-uninstall.py` are stdlib-only and unaffected.

### Changed
- **Leaner `core-context.md`.** Note bodies now have their redundant leading
  `# Title` stripped (the distiller already emits a heading above the body), and
  `## Related` link blocks are dropped from `core-context.md` (they're vault
  navigation, dead weight in always-loaded context). H1 stripping applies to all
  distilled outputs; Related stripping is core-context only. Trimmed the eager
  footprint ~21% with no loss of facts.

### Docs
- Documented **release discipline** in the versioning section: bump `VERSION`
  with the change (or in an immediate `chore: release`), never let MINOR/MAJOR
  commits pile up on a released version. Added a release-commit checklist.
- Documented the interpreter contract in `skills/cortex-ai/SKILL.md`: always use
  plain `python3`; the scripts self-bootstrap into `.venv`.

## [1.2.1] — 2026-07-10

### Changed
- **Docs: overview reframed around the agent-assisted workflow.** The overview
  previously framed Cortex as "a folder of Markdown notes you author in whatever
  editor you like," implying a Markdown editor was the way in. Reframed throughout
  to put in-conversation capture first — the assistant writes knowledge to the
  vault and re-distills as you work — with manual hand-editing presented as an
  option, not a requirement. Touches "What Cortex Is", the Vault layer, the
  comparison table's curation row, and the MemGPT/Mem0 comparisons. Doc-only; no
  behaviour change.

## [1.2.0] — 2026-07-10

### Added
- **`deploy.sh`** — idempotent upgrade of an existing live install whose pieces
  live in separate locations (distiller under `<vault>/_sync/`, MCP under
  `~/.config/opencode/mcp/cortex/`, skill under `~/.config/opencode/skills/`).
  Backs up every target first, re-distills, verifies schema, and auto-fixes the
  skill's MCP path for split layouts. Dry-run by default; refuses to downgrade a
  newer live vault. Locations overridable via `VAULT_ROOT`/`MCP_HOME`/`SKILLS_DIR`.

### Changed
- **`sync` is now capture-then-rebuild.** The `cortex` skill's `sync` command runs
  the capture reflex (scan the session against `vault-capture-rules`, write
  capturable knowledge/decisions/lessons to the vault) *before* running the
  distiller. A bare distiller run re-emits stale knowledge and loses the session's
  lessons, so it no longer counts as a sync on its own.

## [1.1.0] — 2026-07-10

### Added
- **Schema versioning** (`SCHEMA_VERSION`, starting at `1`) decoupled from the
  release SemVer. Stamped into `memory.json._meta.schema_version` and surfaced by
  `distill.py --show-config`.
- **Upgrade safety** in `distill.py`: on every run it compares code vs vault
  schema, auto-backs up `_sync/` and runs registered migrations when the code is
  newer, and refuses to run (rather than corrupt data) when the vault is newer.
- **Migration registry** (`MIGRATIONS` in `distill.py`) — machinery for future
  schema changes; empty at schema `1`.
- **`distill.py --check`** — plain-language release/schema health report.
- **Install manifests** — `setup.sh` and `cortex-import.py` now record every file
  they create/modify/back up under `<vault>/_sync/backups/<stamp>/manifest.json`.
- **`cortex-uninstall.py`** — manifest-driven revert to pre-Cortex state
  (dry-run by default; `--apply`, `--latest`, `--backup`, `--purge`). Keeps notes.
- **`cortex` skill** gained an `uninstall` command and schema-aware `version` /
  `status` output.

## [1.0.0]

Initial release: tiered Obsidian-vault distiller, Cortex MCP server, `cortex-ai`
skill, importer, and `setup.sh` bootstrap.

# CLI Reference

All operations go through the `cortex` command. Run `cortex --help` for the
full list.

---

## cortex bootstrap

Create a Python venv and install dependencies.

```
cortex bootstrap [REPO_ROOT]
```

| Argument | Default | Description |
|----------|---------|-------------|
| `REPO_ROOT` | auto-detect | Path to the Cortex repo root |

**What it does:** Creates `.venv/` (if missing), upgrades pip, installs
`requirements.txt` (or the package in editable mode). Idempotent — safe to
re-run.

```
cortex bootstrap
```

---

## cortex install

Set up or upgrade a Cortex installation.

```
cortex install [VAULT] [--upgrade] [--no-encode] [--dry-run]
```

| Argument / Flag | Default | Description |
|-----------------|---------|-------------|
| `VAULT` | prompt | Vault path (interactive prompt if omitted) |
| `--upgrade` | off | Backup existing files, deploy updates, re-encode |
| `--no-encode` | off | Skip re-encoding (with `--upgrade`) |
| `--dry-run` | off | Preview changes without writing |

**What it does (initial install):**

1. Ensures venv deps are installed (creates venv if needed)
2. Deploys encoder scripts to `<vault>/_sync/`
3. Generates `<vault>/_sync/cortex.yaml` (if missing)
4. Installs the `cortex-ai` skill to `~/.config/opencode/skills/`
5. Runs first encoding

```
cortex install                          # interactive
cortex install ~/Cortex                 # non-interactive
cortex install --upgrade ~/Cortex       # upgrade existing
cortex install --dry-run ~/Cortex       # preview only
cortex install --upgrade --no-encode ~/Cortex  # skip re-encode
```

---

## cortex uninstall

Revert Cortex-installed assets (notes are kept).

```
cortex uninstall --vault VAULT [--latest] [--backup NAME] [--apply] [--purge]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--vault` | prompt | Vault root (required) |
| `--latest` | `true` | Undo only the most recent manifest |
| `--backup NAME` | `None` | Undo a specific backup directory |
| `--apply` | off | Actually make changes (default is dry-run) |
| `--purge` | off | Also delete `_sync/encoded/` |

```
cortex uninstall --vault ~/Cortex --latest          # preview
cortex uninstall --vault ~/Cortex --latest --apply  # revert
cortex uninstall --vault ~/Cortex --latest --apply --purge  # full cleanup
```

---

## cortex encode

Run vault-to-agent encoding.

```
cortex encode [--dry-run] [--list] [--show-config] [--check] [--graph]
               [--purge] [--purge-apply] [--config PATH]
               [--hive-push] [--hive-pull] [--hive-status]
```

| Flag | Description |
|------|-------------|
| `--dry-run` | Preview all writes without touching disk |
| `--list` | List every note with its tier and type |
| `--show-config` | Print resolved paths as JSON |
| `--check` | Report release/schema version health |
| `--graph` | Output wiki-link graph and exit |
| `--purge` | Preview deletion of drained log/session notes |
| `--purge-apply` | Delete drained notes and rebuild |
| `--config PATH` | Path to `cortex.yaml` (default: cwd/_sync/cortex.yaml) |
| `--hive-push` | Push vault notes to Cortex Hub |
| `--hive-pull` | Pull vault notes from Cortex Hub |
| `--hive-status` | Show hive connection status |

```
cortex encode                          # normal run
cortex encode --dry-run                # preview
cortex encode --list                   # see all notes
cortex encode --check                  # version/schema health
cortex encode --show-config            # resolved paths
cortex encode --config ~/Cortex/_sync/cortex.yaml  # explicit config
```

---

## cortex status

Show installation health.

```
cortex status [--vault VAULT]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--vault` | auto-detect | Vault path |

Reports: config found, vault found, encoded memory found, schema version
status, opencode config found.

```
cortex status
cortex status --vault ~/Cortex
```

---

## cortex doctor

Validate installation across all platforms.

```
cortex doctor [--platform NAME] [--vault VAULT]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--platform NAME` | all | Check a specific platform only |
| `--vault` | auto-detect | Vault path |

Checks core assets (config, vault, encoded memory, skill) and each
platform integration (opencode, codex, copilot).

```
cortex doctor
cortex doctor --platform opencode
```

---

## cortex import

Import existing agent context into the vault.

```
cortex import [--vault VAULT] [--dry-run]
              [--agents-md PATH] [--claude-md PATH]
              [--opencode PATH] [--claude-memory PATH]
```

| Flag | Description |
|------|-------------|
| `--vault` | Target vault (auto-detect if omitted) |
| `--dry-run` | Preview without writing |
| `--agents-md` | Path to `AGENTS.md` |
| `--claude-md` | Path to `CLAUDE.md` |
| `--opencode` | Path to `opencode.jsonc` |
| `--claude-memory` | Path to `~/.claude/memory/` directory |

Reads common agent config files, backs them up to
`<vault>/_sync/backups/`, and seeds the vault with notes tagged `review`
for manual refinement.

```
cortex import --dry-run          # preview
cortex import                    # import into auto-detected vault
cortex import --vault ~/Cortex   # explicit vault
```

---

## cortex version

Print version information.

```
cortex version
```

Outputs the release version (`VERSION` file) and schema version
(`SCHEMA_VERSION` file).

---

## cortex memory search

Search encoded memory from the CLI.

```
cortex memory search QUERY [--vault VAULT]
```

| Argument / Flag | Description |
|-----------------|-------------|
| `QUERY` | Search string (required) |
| `--vault` | Vault path (auto-detect if omitted) |

Searches `memory.json` by keyword, ranking across note id, aliases, tags,
category, and body content.

```
cortex memory search jira
cortex memory search "sprint calendar" --vault ~/Cortex
```

---

## cortex memory get

Fetch a single memory note by its id.

```
cortex memory get ID [--vault VAULT]
```

| Argument / Flag | Description |
|-----------------|-------------|
| `ID` | Note id slug (required) |
| `--vault` | Vault path (auto-detect if omitted) |

Looks up the note in `memory.json` first. If not found, falls back to scanning
vault files for `<id>.md`. Returns full content and metadata.

```
cortex memory get askdel
cortex memory get jira-rest-api --vault ~/Cortex
```

---

## cortex lint

Lint a Cortex vault for common issues.

```
cortex lint [--vault VAULT] [--strict] [--fix] [--note ID] [--json] [--rules]
```

| Flag | Description |
|------|-------------|
| `--vault` | Vault path (auto-detect if omitted) |
| `--strict` | Treat warnings as errors |
| `--fix` | Auto-fix fixable issues (missing-type, missing-tier, missing-aliases) |
| `--note ID` | Lint a single note by id |
| `--json` | Output results as JSON |
| `--rules` | List available rules and exit |

**Rules:**

| Severity | Rule | Description | Auto-fix |
|----------|------|-------------|:--------:|
| E | `missing-id` | Note is missing an `id` field in frontmatter | |
| E | `missing-type` | Note is missing a `type` field in frontmatter | ✓ |
| E | `missing-tier` | Note is missing a `tier` field in frontmatter | ✓ |
| E | `invalid-tier` | Note has an unrecognized tier value | |
| E | `duplicate-id` | Multiple files share the same `id` | |
| W | `missing-aliases` | Note is missing an `aliases` field | ✓ |
| W | `slug-mismatch` | Filename stem does not match the `id` field | |
| W | `dangling-wiki-link` | Wiki-link targets a non-existent note | |
| W | `non-slug-id` | `id` contains non-slug characters | |
| I | `missing-updated` | Note is missing an `updated` date | |
| I | `empty-body` | Note has no body content | |

Exit codes: 0 = clean, 1 = errors found.

```
cortex lint                          # scan auto-detected vault
cortex lint --vault ~/Cortex         # explicit vault
cortex lint --strict                 # warnings become errors
cortex lint --fix                    # auto-fix type/tier/aliases
cortex lint --note my-note           # single note
cortex lint --json                   # machine-readable output
cortex lint --rules                  # list rules
```

---

## cortex memory write

Write a memory note to the vault. Without `--body` or `--body-file`, writes
frontmatter only.

```
cortex memory write --title TITLE --type TYPE --tier TIER
                    [--tags TAGS] [--category CAT]
                    [--body TEXT | --body-file PATH]
                    [--update] [--no-encode] [--vault VAULT]
```

| Flag | Description |
|------|-------------|
| `--title` | Note title (becomes alias and id) |
| `--type` | Note type: `knowledge`, `entity`, `feedback`, `session`, `log` |
| `--tier` | Tier: `core`, `skill:<name>`, `project`, `vault-only` |
| `--tags` | Comma-separated tags |
| `--category` | Category label |
| `--body` | Note body content (inline text) |
| `--body-file` | Path to file containing note body content |
| `--update` | Patch an existing note (update body + bump date) |
| `--no-encode` | Skip automatic encode after write (for batch operations) |
| `--vault` | Vault path (auto-detect if omitted) |

Creates or updates a note file with YAML frontmatter and optional body. By
default triggers `cortex encode` in the background after writing.

```
cortex memory write --title "TypeScript Style" --type feedback --tier core
cortex memory write --title "Jira Tips" --type knowledge --tier skill:jira --body "Use JQL for complex queries"
cortex memory write --title "Sprint Notes" --type session --tier vault-only --body-file ./notes.md
cortex memory write --title "Jira Tips" --type knowledge --tier skill:jira --body "Updated content" --update
cortex memory write --title "Batch Item" --type knowledge --tier project --no-encode
```

---

## Platform Commands

Manage agent platform integrations. Each platform supports
`install`, `uninstall`, and `status`.

### cortex opencode

```
cortex opencode install [--vault VAULT] [--dry-run]
cortex opencode uninstall [--vault VAULT] [--dry-run]
cortex opencode status [--vault VAULT]
```

### cortex codex

Stub — not yet implemented.

```
cortex codex install
cortex codex uninstall
cortex codex status
```

### cortex copilot

Stub — not yet implemented.

```
cortex copilot install
cortex copilot uninstall
cortex copilot status
```

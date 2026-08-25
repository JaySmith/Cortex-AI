# Troubleshooting

## Start here: `cortex doctor`

Before chasing a specific error, run the built-in diagnostic. `cortex doctor`
checks your whole installation — core assets *and* every agent platform — in one
pass, and prints a suggested fix beside anything it finds wrong:

```bash
cortex doctor                      # check everything
cortex doctor --platform opencode  # check one platform only
cortex doctor --vault ~/cortex-ai  # explicit vault
```

**What it checks:**

| Section | Checks |
|---------|--------|
| Core | Python ≥ 3.10 · `cortex.yaml` present · vault exists and is writable · schema compatibility · encoded `memory.json` present, valid, and fresh (≤ 7 days) · skill installed |
| Per platform | Whether the platform is detected, and whether its integration validates (opencode, codex, copilot) |

**Reading the symbols:**

- `✓` healthy · `⚠` works but needs attention (e.g. stale memory, migration
  pending) · `✗` broken · `○` skipped because a prerequisite failed.

The run ends with `Status: HEALTHY` or `Status: NEEDS ATTENTION`. If anything is
wrong, most issues clear with `cortex install` (assets) or `cortex encode`
(stale/missing memory) — doctor names the exact command per line.

> `cortex doctor` is the cross-platform superset of `cortex status`. Use `status`
> for a quick single-environment glance; use `doctor` when something is actually
> broken or you want per-platform validation. For version/schema health
> specifically, `cortex encode --check` is the narrowest check.

## Installation

### "python3 not found on PATH"

Install Python 3.10+:

- **macOS:** `brew install python@3.12`
- **Ubuntu:** `sudo apt install python3.12`
- **Windows:** download from [python.org](https://python.org)

Verify: `python3 --version`

### "ERROR: PyYAML is required"

The venv is missing or incomplete. Run:

```bash
cortex bootstrap
```

### "ERROR: vault path does not exist"

The path passed to `cortex install` does not exist. Create it first:

```bash
mkdir -p /path/to/your/vault
cortex install /path/to/your/vault
```

### "WARNING: skill source not found at .../skills/cortex-ai/SKILL.md"

The `skills/cortex-ai/` directory is missing from the repo. Ensure you
cloned the full repository (not a shallow clone) and are running from the
repo root.

### Skill directory missing during encode

```
WARNING: skill dir missing, skipping: /path/to/skills/jira
```

A note has `tier: skill:jira` but the skill directory doesn't exist. Either:

1. The skill needs to be installed (`cortex opencode install`)
2. The note's tier should be changed
3. The skills target can be disabled in `cortex.yaml`

## Encoding

### "Config not found"

```bash
cortex encode --config /path/to/your/vault/_sync/cortex.yaml
```

Or ensure `_sync/cortex.yaml` exists. `cortex install` generates it
automatically.

### "vault_path does not exist"

Check the `vault_path` in `cortex.yaml`. It must point to an existing
directory.

### Notes are being skipped

Notes are silently skipped when:

- They have no `type` field in frontmatter
- Their `tier` is `vault-only`
- Their type is in `vault_only_types` (default: session, log)
- Their tags are in `exclude_tags` (default: draft, archived)

Check with `cortex encode --list` to see all notes and their tier/type.

### Distilled output is stale

Run `cortex encode` to rebuild. If you edited notes and the output hasn't
changed, check that the notes have valid frontmatter with `type` and `tier`.

## Schema / Versioning

### "live vault schema is NEWER than this code"

The vault was created with a newer Cortex version. Pull the latest code:

```bash
git pull
cortex install --upgrade /path/to/your/vault
```

### Schema migration pending

```bash
cortex encode --check
```

If it reports a migration is pending, run `cortex install --upgrade` to
migrate and re-encode.

### "Schema: unknown (fresh vault?)"

The vault has no `_meta` in `memory.json`. Run `cortex encode` to generate
it.

## CLI Memory Commands

### opencode not finding memory commands

1. Ensure the cortex-ai skill is installed: `cortex opencode status`
2. If missing, run `cortex opencode install`
3. Restart opencode to pick up changes
4. Verify at the terminal: `cortex memory search "."`

### Skill not loading in opencode

Ensure the skill is installed:

```bash
ls ~/.config/opencode/skills/cortex-ai/SKILL.md
```

If missing, run `cortex opencode install` or `cortex install`.

### "Config: not found" from cortex status

Cortex isn't installed in this environment. Run:

```bash
cortex bootstrap
cortex install /path/to/your/vault
```

## General

### How do I see what notes exist?

```bash
cortex encode --list
```

### How do I preview changes before writing?

```bash
cortex encode --dry-run
```

### How do I check version/schema health?

```bash
cortex encode --check
cortex status
```

### How do I search memory from the CLI?

```bash
cortex memory search "your query"
```

### How do I undo a Cortex install?

```bash
cortex uninstall --vault /path/to/your/vault --latest          # preview
cortex uninstall --vault /path/to/your/vault --latest --apply  # revert
```

Your vault notes are always preserved.

# Development Guide

How to set up this repo for **contributing to Cortex itself** — editing the
encoder, CLI, or skill. If you just want to *use* Cortex, see the
[README](../README.md) and [QUICKSTART](./QUICKSTART.md) instead.

## Prerequisites

- **Python 3.10+**
- **git**

## Repo vs. live install — read this first

Cortex has two distinct locations, and confusing them is the single biggest
source of wasted time when developing:

| | Path | What it is |
|---|------|------------|
| **Repo (gold standard)** | `~/Projects/Cortex-AI` | The git-tracked source. **Always edit here first.** |
| **Live install** | split across locations (below) | Copies the running agent actually loads. |

The live install is **not** a checkout of the repo — its pieces are copied to:

| Piece | Live location |
|-------|---------------|
| Config | `<vault>/_sync/cortex.yaml` |
| Skill (`SKILL.md` with paths expanded) | `~/.config/opencode/skills/cortex-ai/` |
| Vault (notes + encoded output) | `<vault>/` |
| Python venv | `<repo>/.venv/` |

Consequences:

- **`git pull` does nothing to the live install.** You must redeploy — see
  [The dev loop](#the-dev-loop).
- **Never copy a deployed `SKILL.md` back into the repo.** The deployed copy
  has paths expanded to machine-specific values; the repo keeps placeholders.
- **Never patch the live install directly** — `cortex install --upgrade` will
  overwrite it on the next deploy.

## First-time setup

```bash
git clone https://github.com/JaySmith/Cortex-AI.git cortex-ai
cd cortex-ai

cortex bootstrap

# Install for development (editable mode)
.venv/bin/pip install -e ".[dev]"
```

`build/` and `.venv/` are gitignored — they're generated, never committed.

## Working on the encoder (`cortex/encoder/core.py`)

Use the bundled `example-vault/` as a sandbox — it has one note per tier and
works out of the box, with no risk to a real vault.

```bash
cortex encode --config example-vault/_sync/cortex.yaml --dry-run
cortex encode --config example-vault/_sync/cortex.yaml --list
cortex encode --config example-vault/_sync/cortex.yaml
```

Useful flags:

| Flag | Purpose |
|------|---------|
| `--dry-run` | Preview all writes without touching disk |
| `--list` | List every note with its tier + type |
| `--show-config` | Print resolved paths as JSON |
| `--check` | Report release/schema versions and whether a migration is pending |
| `--purge` / `--purge-apply` | Preview / delete drained log/session notes |

There's no unit-test suite; the workflow is `--dry-run` against
`example-vault/`, eyeball the output, then run for real. Keep edits
idempotent — re-running on unchanged input must produce no writes.

## The dev loop

The safe, repeatable cycle for a change that touches the live install:

```bash
# 1. Edit in the repo (never the live install)
#    cortex/encoder/core.py / skills/cortex-ai/SKILL.md

# 2. Preview the deploy (changes nothing)
cortex install --upgrade --dry-run ~/Cortex

# 3. Apply, then restart your agent to load the new skill
cortex install --upgrade ~/Cortex
```

`cortex install --upgrade` backs up every live target first, copies repo
files into their live locations, renders `SKILL.md` (expanding path
placeholders), re-encodes the live vault, and verifies versions/schema
match. It is idempotent and refuses to downgrade a newer vault.

## Running the tests

```bash
.venv/bin/pip install -e ".[dev]"     # once
.venv/bin/python -m pytest            # run all
```

`conftest.py` copies `example-vault/` into a tmp dir per test, so tests
never touch your real vault.

## Quality checks

All quality tools are installed via `pip install -e ".[dev]"`. Run before
every commit:

```bash
ruff check .              # lint
ruff format --check .     # format check
mypy cortex/cli cortex/config  # type check (new modules only)
pytest                     # tests
```

Fix auto-fixable issues:

```bash
ruff check --fix .        # auto-fix lint
ruff format .             # auto-format
```

### Pre-commit hooks

```bash
.venv/bin/pre-commit install
```

Hooks run ruff (lint + format) and basic file checks. To run manually:

```bash
.venv/bin/pre-commit run --all-files
```

### CI

GitHub Actions runs on every push/PR to `main` (`.github/workflows/ci.yml`):
ruff check, ruff format, mypy, and pytest.

## Cutting a release

Cortex tracks two numbers (full rules in [CHANGELOG.md](../CHANGELOG.md)):

- **Release version** — SemVer in `VERSION`. Bump for any user-visible change.
- **Schema version** — integer in `SCHEMA_VERSION`. Bump only when the
  on-disk data contract changes, with a migration in the encoder.

Release checklist:

1. Bump `VERSION` (and `SCHEMA_VERSION` + migration if contract changed).
2. Promote CHANGELOG `[Unreleased]` to `[x.y.z] — YYYY-MM-DD`.
3. Commit as `chore: release x.y.z`.
4. Deploy: `cortex install --upgrade ~/Cortex`, then restart the agent.
5. Verify: `cortex encode --check` should report both versions in sync.

## Reverting a broken deploy

```bash
cortex uninstall --vault ~/Cortex --latest          # preview
cortex uninstall --vault ~/Cortex --latest --apply  # revert
```

## See also

- [EXTENDING.md](./EXTENDING.md) — add a custom output target to the encoder
- [VAULT_SCHEMA.md](./VAULT_SCHEMA.md) — frontmatter reference
- [CHANGELOG.md](../CHANGELOG.md) — versioning rules in full

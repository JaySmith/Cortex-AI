# Development Guide

How to set up this repo for **contributing to Cortex itself** — editing the
distiller, the MCP server, or the skill. If you just want to *use* Cortex, see the
[README](../README.md) and [QUICKSTART](./QUICKSTART.md) instead.

## Prerequisites

- **Python 3.10+** — the distiller uses modern type-hint syntax (`str | None`).
- **Node 18+** — the MCP server is TypeScript, compiled with `tsc`.
- **git**

## Repo vs. live install — read this first

Cortex has two distinct locations, and confusing them is the single biggest
source of wasted time when developing:

| | Path | What it is |
|---|------|------------|
| **Repo (gold standard)** | `~/Projects/cortex-ai` | The git-tracked source. **Always edit here first.** |
| **Live install** | split across three dirs (below) | Hand-assembled *copies* the running agent actually loads. |

The live install is **not** a checkout of the repo — its pieces are copied to:

| Piece | Live location |
|-------|---------------|
| Distiller + companions (`distill.py`, `gen-portfolio.py`, `cortex-*.py`, `VERSION`, `SCHEMA_VERSION`, `CHANGELOG.md`) | `<vault>/_sync/` |
| MCP server (`build/`, `package.json`, `VERSION`) | `~/.config/opencode/mcp/cortex/` |
| Skill (`SKILL.md`, with `<CORTEX_HOME>` expanded to real paths) | `~/.config/opencode/skills/cortex-ai/` |
| Vault (notes + distilled output) | `<vault>/` (e.g. `~/Cortex`) |
| Python venv the MCP invokes | `<vault>/_sync/.venv/bin/python` |

Consequences:

- **`git pull` does nothing to the live install.** You must redeploy — see
  [The dev loop](#the-dev-loop).
- **Never copy a deployed `SKILL.md` back into the repo.** The deployed copy has
  `<CORTEX_HOME>` expanded to machine-specific paths; the repo keeps the
  placeholder. Re-apply skill edits to the repo version by hand. (`distill.py` and
  `CHANGELOG.md` have no hardcoded paths, so copying *those* back is safe.)
- **Never patch the live install directly** — `deploy.sh` will overwrite it on the
  next deploy, silently losing your change.

## First-time setup

```bash
git clone https://github.com/JaySmith/Cortex-AI.git cortex-ai
cd cortex-ai

# 1. Python side (distiller). Add requirements-dev.txt to run the test suite.
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt

# 2. Node side (MCP server)
cd mcp/cortex
npm install
npm run build
cd ../..
```

`build/` and `.venv/` are gitignored — they're generated, never committed.

### Why the venv matters

`distill.py` and `gen-portfolio.py` import PyYAML, which lives **only** in the
sibling `.venv` — the macOS Homebrew system Python is externally-managed and can't
`pip install`. Both scripts **self-bootstrap**: they `os.execv` into
`.venv/bin/python` before importing PyYAML, so `python3 distill.py` works from any
interpreter once the venv exists. If you see `ERROR: PyYAML is required`, the venv
isn't set up — run step 1 above.

## Working on the distiller (`distill.py`)

Use the bundled `example-vault/` as a sandbox — it has one note per tier and works
out of the box, with no risk to a real vault.

```bash
# Point at the example vault's config
python3 distill.py --config example-vault/_sync/cortex.yaml --dry-run
python3 distill.py --config example-vault/_sync/cortex.yaml --list
python3 distill.py --config example-vault/_sync/cortex.yaml
```

Useful flags:

| Flag | Purpose |
|------|---------|
| `--dry-run` | Preview all writes without touching disk |
| `--list` | List every note with its tier + type |
| `--show-config` | Print resolved paths as JSON (what the code actually uses) |
| `--check` | Report release/schema versions and whether a migration is pending |
| `--purge` / `--purge-apply` | Preview / delete drained log/session notes |

There's no unit-test suite; the workflow is `--dry-run` against `example-vault/`,
eyeball the output, then run for real. Keep edits idempotent — re-running the
distiller on unchanged input must produce `unchanged` for every target.

## Working on the MCP server (`mcp/cortex/`)

Source is TypeScript in `mcp/cortex/src/`; `tsc` compiles it to `build/`
(gitignored). The server reads `VERSION` at runtime, so it always reports the
version of whatever install it's launched from.

```bash
cd mcp/cortex

npm run build        # one-off compile (prebuild syncs package.json to VERSION)
npm run dev          # tsc --watch — recompile on save
npm run inspector    # launch the MCP Inspector against the built server for
                     # interactive tool testing (memory_search, memory_write, ...)
```

The `inspector` target is the fastest way to exercise tools by hand without wiring
the server into an agent.

## The dev loop

The safe, repeatable cycle for a change that touches the live install:

```bash
# 1. Edit in the repo (never the live install)
#    distill.py / mcp/cortex/src/*.ts / skills/cortex-ai/SKILL.md

# 2. If you touched the MCP, rebuild it
(cd mcp/cortex && npm run build)

# 3. Preview the deploy (changes nothing)
./deploy.sh

# 4. Apply, then restart your agent to load the new MCP build + skill
./deploy.sh --apply
```

`deploy.sh` backs up every live target first, copies the repo files into their
split locations, **renders `SKILL.md`** (expanding `<CORTEX_HOME>` to the real
paths), re-distills the live vault, and verifies versions/schema match. It is
idempotent and refuses to downgrade a live vault that's newer than the code.

Override locations with `VAULT_ROOT`, `MCP_HOME`, `SKILLS_DIR` env vars;
`--no-distill` skips the final re-distill.

## Running the tests

The pytest suite lives in `tests/` and needs `pytest` (declared in
`requirements-dev.txt`, not the runtime `requirements.txt`):

```bash
.venv/bin/pip install -r requirements-dev.txt   # once
.venv/bin/python -m pytest                       # run all
```

`conftest.py` copies `example-vault/` into a tmp dir per test, so tests never
touch your real vault.

## Cutting a release

Cortex tracks two numbers (full rules in [CHANGELOG.md](../CHANGELOG.md)):

- **Release version** — SemVer in `VERSION`. Bump for any user-visible change.
- **Schema version** — integer in `SCHEMA_VERSION`. Bump **only** when the on-disk
  data contract changes, and add a migration in `distill.py`'s `MIGRATIONS`
  registry.

Release checklist:

1. Bump `VERSION` (and `SCHEMA_VERSION` + a migration if the contract changed).
2. Promote CHANGELOG `[Unreleased]` → `[x.y.z] — YYYY-MM-DD`.
3. Rebuild the MCP so `package.json` syncs: `(cd mcp/cortex && npm run build)`.
   Also bump the root `version` in `mcp/cortex/package-lock.json` to match (the
   prebuild hook only updates `package.json`).
4. Commit as `chore: release x.y.z`.
5. Deploy: `./deploy.sh --apply`, then restart the agent.
6. Verify: `python3 <vault>/_sync/distill.py --config <vault>/_sync/cortex.yaml --check`
   should report both versions and `schema in sync`.

**Release discipline:** bump the version *with* the change, or in an immediate
`chore: release`. Never let MINOR/MAJOR commits pile up on an already-released
version — the version stops describing what's shipped. PATCH-only changes may
accumulate under `[Unreleased]`.

## Reverting a broken deploy

Every `deploy.sh --apply` writes a timestamped backup under
`<vault>/_sync/backups/<stamp>-deploy-<version>/`. To roll back, copy those files
back into their live locations, or use `cortex-uninstall.py` for a full revert
(your notes are always kept):

```bash
python3 cortex-uninstall.py --vault <vault> --latest          # preview
python3 cortex-uninstall.py --vault <vault> --latest --apply  # revert
```

## See also

- [EXTENDING.md](./EXTENDING.md) — add a custom output target to the distiller
- [VAULT_SCHEMA.md](./VAULT_SCHEMA.md) — frontmatter reference
- [DISTILLATION_SUMMARY.md](./DISTILLATION_SUMMARY.md) — architecture
- [mcp/cortex/README.md](../mcp/cortex/README.md) — MCP server internals + tools
- [CHANGELOG.md](../CHANGELOG.md) — versioning rules in full

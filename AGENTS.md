# Cortex-AI — Agent Instructions

## Repo is the source of truth, not the live install

When designing, planning, or reasoning about features, **this repo is the source
of truth**. The deployed/live install is a *deployment target*, not a design
surface.

- **Feature / design / planning work** → read and reason about files in **this
  repo only**. For skills, that means `skills/` here — NOT
  `~/.config/opencode/skills/`.
- **Read the live install ONLY when:**
  1. The user explicitly asks about the live/deployed state, OR
  2. We are running or verifying a deployment (`setup.sh` / `deploy.sh`), OR
  3. We are diagnosing a bug that only reproduces in the deployed environment.

### Why

`skills/` holds the canonical templates. `setup.sh` and `deploy.sh` render them
into `~/.config/opencode/skills/`, injecting machine-specific paths. The deployed
copies drift and accumulate sediment. Reasoning about the live install during
design work means reasoning about stale, personalized artifacts instead of the
clean source.

### When unsure

If it's ambiguous whether a request is about the repo or the live install, assume
**repo** and ask before touching the live install.

## Layout

- `skills/` — canonical skill templates (source of truth for skills)
- `distill.py`, `hive_client.py`, `cortex-*.py` — Python tooling
- `mcp/cortex/` — MCP server (TypeScript, built to `build/`)
- `setup.sh` — fresh bootstrap; `deploy.sh` — upgrade an existing install
- `tests/` — pytest suite (`conftest.py` copies `example-vault` into tmp)
- `docs/` — conventions and schema references

## Commands

- **Test:** `pytest`
- **Build MCP:** `cd mcp/cortex && npm run build`
- **Distill:** `python3 distill.py --config <cortex.yaml>`

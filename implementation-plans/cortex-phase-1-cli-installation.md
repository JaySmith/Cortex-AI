# Cortex Phase 1 — Product-Grade CLI & Installation

## Agent Implementation Brief

### Objective

Transform Cortex from a collection of standalone scripts into a cohesive, installable command-line product.

Current experience:

```bash
git clone https://github.com/JaySmith/Cortex-AI.git cortex-ai
cd cortex-ai
./setup.sh
```

Target experience:

```bash
uv tool install cortex-ai
cortex install
```

The goal is to make Cortex feel like a polished product: simple to install, easy to validate, and consistent to operate.

---

## Background

Cortex currently exposes core capabilities through scripts such as:

```text
setup.sh
distill.py
cortex-import.py
cortex-uninstall.py
deploy.sh
```

These scripts work, but the user experience requires the user to know which
script to run and when. This phase consolidates user-facing operations behind a
single `cortex` CLI.

---

## Scope

### In Scope

- Create a Python package layout for Cortex.
- Add a first-class CLI entry point.
- Wrap existing setup, distill, import, uninstall, status, and version behavior in commands.
- Preserve existing behavior while improving discoverability.
- Add basic installation validation.

### Out of Scope

- Full multi-agent installer framework.
- Advanced diagnostics.
- Major schema redesign.
- Large refactors unrelated to CLI packaging.

---

## Target Repository Structure

Create or migrate toward this structure:

```text
cortex/
  __init__.py
  cli/
    __init__.py
    main.py
    commands/
      __init__.py
      install.py
      uninstall.py
      distill.py
      status.py
      memory.py
      import_agent.py
      version.py
  config/
    __init__.py
  distiller/
    __init__.py
  memory/
    __init__.py
  mcp/
    __init__.py

docs/
tests/
pyproject.toml
README.md
```

The agent should preserve existing scripts during migration unless they can be safely replaced.

---

## Module Rename Map

The existing root scripts use hyphens (not importable as modules) and have one
cross-script dependency: `distill.py` does `from hive_client import ...`. Port in
this order so imports never break:

```text
hive_client.py        → cortex/hub/client.py        (move FIRST — distill.py imports it)
cortex-mcp-upsert.py  → cortex/mcp/upsert.py
cortex-import.py      → cortex/commands/import_agent.py
cortex-uninstall.py   → cortex/commands/uninstall.py
distill.py            → cortex/distiller/core.py     (update its hive import to cortex.hub.client)
```

`gen-portfolio.py` is not user-facing plumbing and can stay a root script for now.

---

## CLI Framework

Use either `typer` or `click`. Prefer `typer` for readable command definitions and better help output.

Add dependency in `pyproject.toml`:

```toml
[project]
name = "cortex-ai"
version = "1.4.0"
description = "Persistent, tiered memory for AI coding agents"
requires-python = ">=3.10"
dependencies = [
  "typer>=0.12",
  "PyYAML>=6.0",
]

[project.scripts]
cortex = "cortex.cli.main:app"

[tool.setuptools.package-data]
cortex = ["templates/**/*", "../mcp/cortex/build/**/*"]
```

Note: the package version continues the existing version line (`VERSION` = `1.4.0`,
MCP server = `1.4.0`) rather than resetting to `0.1.0`. Keep `pyproject.toml` in
sync with the `VERSION` file — read it dynamically or pin it to match.

---

## Required Commands

Implement the following commands.

### `cortex install`

Purpose: bootstrap Cortex for a user.

Responsibilities:

- Prompt for vault location.
- Prompt for agent/platform location when needed.
- Generate `<vault>/_sync/cortex.yaml` from the `cortex.yaml.example` schema
  (port the config-generation logic from `setup.sh`).
- Install required Python dependencies if needed.
- Copy the bundled `mcp/cortex/build/` (shipped as package data) to
  `~/.config/opencode/mcp/cortex/`. Do not require Node at install time — the
  build is pre-compiled and bundled.
- Run first distillation.
- Print next steps.

Expected UX:

```bash
cortex install
```

Example output:

```text
Cortex install

Vault: ~/Documents/cortex-vault
Agent: OpenCode

✓ Config created
✓ MCP server configured
✓ First distillation completed
✓ Cortex skill installed

Next: run cortex status
```

### `cortex uninstall`

Purpose: safely revert Cortex-installed assets while preserving user notes.

Responsibilities:

- Detect latest install manifest or backup.
- Preview changes by default.
- Require explicit apply flag for destructive changes.

Expected UX:

```bash
cortex uninstall
cortex uninstall --apply
```

### `cortex distill`

Purpose: run the vault-to-agent distillation process.

Responsibilities:

- Load config.
- Run existing distillation logic.
- Support dry run.
- Support list and config display if existing functionality supports it.

Expected UX:

```bash
cortex distill
cortex distill --dry-run
cortex distill --list
cortex distill --show-config
```

### `cortex status`

Purpose: show basic health of Cortex.

Responsibilities:

- Confirm config exists (searches the default `<vault>/_sync/cortex.yaml` path
  used by `setup.sh`; no `--config` flag required).
- Confirm vault path exists.
- Confirm distilled output exists.
- Confirm memory file exists.
- Confirm schema version compatibility if available.

Expected UX:

```bash
cortex status
```

Example output:

```text
Cortex status

Config: found
Vault: found
Distilled memory: found
Schema: compatible
MCP config: found

Status: HEALTHY
```

### `cortex memory search`

Purpose: search distilled memory from the CLI.

Expected UX:

```bash
cortex memory search "deployment preferences"
```

### `cortex memory write`

Purpose: write a memory note from the CLI.

Scope for Phase 1: **metadata only.** The command accepts `--title`, `--type`,
`--tier`, and `--tags` and creates the note with valid frontmatter and an empty
body. Body input (editor/stdin) is deferred to Phase 4.

Expected UX:

```bash
cortex memory write --title "Agent preference" --type feedback --tier core
```

### `cortex import`

Purpose: import existing agent context into Cortex.

Expected UX:

```bash
cortex import
cortex import --dry-run
```

### `cortex version`

Purpose: print Cortex version information.

Expected UX:

```bash
cortex version
```

Example output:

```text
Cortex: 1.4.0
Schema: 2
MCP: 1.4.0
```

---

## Implementation Guidance

1. Start by wrapping existing scripts instead of rewriting all internals.
2. Move reusable logic into importable Python modules.
3. Keep shell scripts temporarily as compatibility shims.
4. Add clear CLI help text for every command.
5. Ensure all commands fail with helpful error messages.

---

## Compatibility Requirements

Existing usage should continue to work during this phase:

```bash
./setup.sh
python distill.py
python cortex-import.py
python cortex-uninstall.py
```

When porting a script, leave the original at repo root as a shim that prints a
deprecation warning and delegates to the new CLI. Remove shims only after Phase 2
CI confirms the test suite passes against the packaged modules.

---

## Acceptance Criteria

The phase is complete when all of the following pass:

```bash
uv tool install .
cortex --help
cortex install
cortex status
cortex distill
cortex version
```

Expected result:

- `cortex --help` lists all major commands.
- `cortex install` completes without manual script execution.
- `cortex status` reports the installation as healthy.
- Existing scripts still work or provide safe migration guidance.

---

## Test Plan

Create tests for:

- CLI command registration.
- Config loading.
- Install command dry-run behavior.
- Status command output.
- Version command output.
- Memory search command behavior with a sample memory file.

The existing tests import root scripts via `sys.path.insert`. After porting,
update those imports to `cortex.*` module paths (e.g. `from cortex.distiller.core
import scan_vault`) so tests exercise the packaged code.

Suggested test command:

```bash
pytest tests/test_cli.py
```

---

## Done Definition

This phase is done when Cortex can be installed and operated through a single
`cortex` command without requiring the user to know the underlying script names.

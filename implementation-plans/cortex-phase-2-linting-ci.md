# Cortex Phase 2 — Engineering Quality, Linting & CI

## Agent Implementation Brief

### Objective

Bring Cortex engineering quality to a professional, contribution-ready standard
by adding formatting, linting, typing, tests, pre-commit hooks, and continuous
integration.

The goal is to make every change safer, easier to review, and less likely to
break installation, distillation, memory operations, or MCP behavior.

---

## Background

Cortex is moving from script-based utility toward product-grade CLI tooling. Once
Phase 1 introduces a formal package and CLI, Phase 2 adds the quality gates
needed to keep the codebase stable as it grows.

This phase should prioritize:

- Consistent formatting.
- Fast linting.
- Type safety in public interfaces.
- Repeatable tests.
- CI enforcement.
- Contributor-friendly defaults.

---

## Scope

### In Scope

- Add Ruff for linting and formatting.
- Add MyPy for type checking.
- Add Pytest for automated tests.
- Add pre-commit hooks.
- Add GitHub Actions CI.
- Add basic test coverage for critical modules.
- Document local development commands.

### Out of Scope

- Large product feature work.
- Major CLI redesign.
- Multi-agent installer support.
- Performance optimization unless required for tests.

---

## Tooling Requirements

### Ruff

Use Ruff for both linting and formatting.

Add development dependency:

```toml
[project.optional-dependencies]
dev = [
  "ruff>=0.5",
  "mypy>=1.10",
  "pytest>=8.0",
  "pre-commit>=3.7",
]
```

Add configuration:

```toml
[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = [
  "E",
  "F",
  "I",
  "B",
  "UP",
]
ignore = []

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
line-ending = "auto"
```

Required commands:

```bash
ruff check .
ruff format .
```

---

### MyPy

Use MyPy to type-check public interfaces and core internal modules.

Add configuration:

```toml
[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false
check_untyped_defs = true
no_implicit_optional = true

[[tool.mypy.overrides]]
module = [
  "cortex.distiller.core",
  "cortex.commands.import_agent",
  "cortex.commands.uninstall",
  "cortex.mcp.upsert",
  "cortex.hub.client",
]
ignore_errors = true
```

The `overrides` block excludes the modules ported from the previously-untyped
root scripts. New code (`cortex/cli`, `cortex/config`, `cortex/memory`) must be
typed; ported modules are typed incrementally in a later pass.

Initial goal:

- Type public CLI functions.
- Type config objects.
- Type memory schema models.
- Type distillation inputs and outputs.
- Type MCP tool request/response models where practical.

Required command (new typed modules only; ported modules excluded via overrides):

```bash
mypy cortex/cli cortex/config cortex/memory
```

---

### Pytest

Extend the **existing** `tests/` directory — do not recreate it. It already
holds `conftest.py` and four test files (`test_distill.py`, `test_cortex_import.py`,
`test_hive_client.py`, `test_mcp_upsert.py`) with 120+ tests.

The vault fixture already exists as `example-vault/` at repo root, copied into a
`tmp_path` by the `vault` fixture in `conftest.py`. Reuse it — do NOT create a
separate `tests/fixtures/sample-vault/`.

Add new test files alongside the existing ones as CLI modules land:

```text
tests/
  conftest.py            (exists — vault + vault_notes fixtures)
  test_distill.py        (exists)
  test_cortex_import.py  (exists)
  test_hive_client.py    (exists)
  test_mcp_upsert.py     (exists)
  test_cli.py            (new)
  test_config.py         (new)
  test_memory.py         (new)
```

Minimum test coverage should include:

- Config load from a known path.
- Config error when file is missing.
- Distillation creates expected output files from sample vault.
- Memory search returns expected note.
- Memory write creates a note with valid frontmatter.
- CLI `--help` works.
- CLI `version` works.
- CLI `status` works against a fixture install.

Required command:

```bash
pytest
```

---

## Pre-Commit

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-json
      - id: check-added-large-files
```

Optional: add MyPy as a local hook once the codebase is typed enough to avoid slowing down normal commits.

Install locally:

```bash
pre-commit install
pre-commit run --all-files
```

---

## GitHub Actions CI

Create:

```text
.github/workflows/ci.yml
```

Required jobs:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install package
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Ruff check
        run: ruff check .

      - name: Ruff format check
        run: ruff format --check .

      - name: MyPy
        run: mypy cortex/cli cortex/config cortex/memory

      - name: Tests
        run: pytest
```

---

## Development Documentation

Create or update:

```text
docs/development.md
```

Include:

```bash
pip install -e ".[dev]"
pre-commit install
ruff check .
ruff format .
mypy cortex/cli cortex/config cortex/memory
pytest
```

Also include the expected contribution flow:

```text
1. Create branch
2. Make change
3. Run format/lint/test locally
4. Commit
5. Open PR
6. CI must pass
```

---

## Acceptance Criteria

This phase is complete when all commands pass locally and in CI:

```bash
ruff check .
ruff format --check .
mypy cortex/cli cortex/config cortex/memory
pytest
pre-commit run --all-files
```

The MyPy gate applies only to the new typed modules (`cortex/cli`,
`cortex/config`, `cortex/memory`). Modules ported from the legacy root scripts are
excluded via `[[tool.mypy.overrides]]` until typed in a later pass.

CI must fail if:

- Code is not formatted.
- Ruff finds lint errors.
- MyPy finds configured type errors.
- Tests fail.

---

## Test Plan

1. Introduce a formatting issue and confirm `ruff format --check .` fails.
2. Introduce an unused import and confirm `ruff check .` fails.
3. Break a typed public interface and confirm `mypy cortex/cli cortex/config cortex/memory` fails.
4. Break a fixture distillation test and confirm `pytest` fails.
5. Push a branch and confirm GitHub Actions runs all jobs.

---

## Done Definition

This phase is done when Cortex has repeatable local quality checks and CI gates
that protect the main branch from formatting, linting, typing, and test failures.

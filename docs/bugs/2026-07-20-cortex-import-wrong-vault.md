# Bug Fix Brief: `cortex import` writes to the wrong vault

- **Status:** Open
- **Reported:** 2026-07-20
- **Affected version:** 1.4.0
- **Component:** `cortex import` CLI command

## Symptom

Running `cortex import` (no `--vault`) on a machine whose vault is `~/cortex-ai/`
wrote the imported notes to `~/feedback/` (i.e. `Path.home()/feedback`) instead of
`~/cortex-ai/feedback/`. The vault was never detected, so it silently defaulted to
the current working directory.

## Root cause

**File:** `cortex/cli/main.py`, function `import_cmd` (the
`@app.command(name="import")` handler), lines **709-717**:

```python
# Auto-detect vault if not provided
if not vault:
    for p in [Path.cwd(), Path.home() / "Cortex"]:
        cfg = p / "_sync" / "cortex.yaml"
        if cfg.exists():
            vault = str(p)
            break
    if not vault:
        vault = str(Path.cwd())
```

This inline detection only checks two hardcoded locations:

1. `Path.cwd()`
2. `Path.home() / "Cortex"` — a hardcoded, capitalized `Cortex` dir name

It does **not** scan the home directory for the real vault, and the vault dir is
commonly named differently (e.g. `cortex-ai`). When neither matches, it falls
through to `Path.cwd()` — the wrong directory — with no warning.

## The correct pattern already exists

The same file has a shared helper `_find_vault()` (lines **100-109**) that every
other command uses (`encode`, `status`, etc. — see lines 1290, 1378, 1512 via
`Path(vault) if vault else _find_vault()`):

```python
def _find_vault() -> Path:
    """Try to find an existing vault by scanning home for _sync/cortex.yaml."""
    cwd = Path.cwd()
    if (cwd / "_sync" / "cortex.yaml").exists():
        return cwd
    home = Path.home()
    for p in home.iterdir():
        if p.is_dir() and (p / "_sync" / "cortex.yaml").exists():
            return p
    return Path.cwd()
```

`import_cmd` is the **only** command that reimplements detection instead of
calling this helper. Had it used `_find_vault()`, the `home.iterdir()` scan would
have found `~/cortex-ai/`.

## Required fix

Replace the inline block (lines 709-717) with the shared helper, matching the
pattern used by the other commands:

```python
vault_path = Path(vault).expanduser() if vault else _find_vault()
import_agent_module.run_import(
    vault=vault_path,
    ...
)
```

(Delete lines 709-719 and use `_find_vault()` for the default.)

## Recommended hardening (worth including)

`_find_vault()` itself still silently returns `Path.cwd()` when no vault is found —
the deeper cause of "wrote to the wrong place with no warning." Consider one of:

- Make `import_cmd` **print the resolved vault and refuse to write** if the
  resolved path lacks `_sync/cortex.yaml`, telling the user to pass `--vault`
  explicitly. (`run_import` already checks `vault.exists()` but not that it's
  actually a vault.)
- Or add a guard in `run_import` (`cortex/cli/commands/import_agent.py`, after
  line 245) that errors if `vault / "_sync" / "cortex.yaml"` is missing, rather
  than happily creating `feedback/` in an arbitrary directory.

Also note: `_find_vault()`'s `home.iterdir()` is non-deterministic if multiple
vaults exist under home, and can raise `PermissionError` on some entries — a
`try/except` per entry would make it robust. Optional, but flag it.

## Tests to add

`tests/test_cortex_import.py` currently tests only pure helpers (`slugify`,
`strip_jsonc`, `build_note`, `first_existing`) — **there is no test for vault
auto-detection**, which is why this regressed. Add tests (use `tmp_path` +
monkeypatch `Path.home`/`Path.cwd`, and Typer's `CliRunner` for the command):

1. Vault dir named something other than `Cortex` (e.g. `cortex-ai`) under a fake
   home → import resolves to that vault's `feedback/`, **not** `home/feedback/`.
2. CWD is the vault → resolves to CWD.
3. No vault anywhere → import errors/warns (per the hardening choice) instead of
   silently writing to CWD.

## Verification

```bash
cd /Users/smithjay/Projects/Cortex-AI
pytest tests/test_cortex_import.py
pytest
```

Then a manual dry-run smoke test from a non-vault CWD: `cortex import --dry-run`
should report the real vault path.

## Also worth noting (separate, smaller)

The `run_import` "next steps" message (`import_agent.py:312`) and the standalone
`main()` argparse default (`import_agent.py:329`, defaults to bundled
`example-vault`) are inconsistent with the Typer command's detection. Not the bug,
but if you touch this area, aligning them avoids future confusion.

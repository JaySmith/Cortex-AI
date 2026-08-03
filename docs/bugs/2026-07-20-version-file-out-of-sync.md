# Bug Fix Brief: VERSION file out of sync with CHANGELOG

- **Status:** Fixed
- **Reported:** 2026-07-20
- **Affected version:** 2.0.0 (shipped), VERSION file claims 1.4.0
- **Component:** `VERSION`, `pyproject.toml`, `cortex/__init__.py`

## Symptom

`cortex version` reports `1.4.0`. The `CHANGELOG.md` and `roadmap.md` both
describe `2.0.0` as shipped on 2026-07-20. Any consumer of `VERSION` —
`cortex version`, the encode `--check` output, upgrade-safety comparisons,
and the MCP server's `serverInfo.version` — is reporting the wrong value.

## Root cause

The 2.0.0 release updated `CHANGELOG.md` and `roadmap.md` but did not bump the
three files that actually carry the version at runtime:

| File | Current | Should be |
|---|---|---|
| `VERSION` (line 1) | `1.4.0` | `2.0.0` |
| `pyproject.toml` (`version =`, line 3) | `1.4.0` | `2.0.0` |
| `cortex/__init__.py` (`__version__`, line 3) | `1.4.0` | `2.0.0` |

The CHANGELOG discipline section (lines 43–50) explicitly requires bumping
`VERSION` in the same commit as the changelog promotion — that step was skipped.

## Fix

Three one-line changes:

```
VERSION                    1.4.0  ->  2.0.0
pyproject.toml             version = "1.4.0"  ->  version = "2.0.0"
cortex/__init__.py         __version__ = "1.4.0"  ->  __version__ = "2.0.0"
```

## Verification

```bash
cortex version
# Expected:
# Cortex:  2.0.0
# Schema:  2
```

## Type

PATCH fix — no behavior change, no schema change. Corrects a tracking error
only.

## Note

The vault-resolution improvement (`CORTEX_VAULT` env var, `~/cortex-ai` default,
`_resolve_vault()`) is separate work planned for **v2.1.0**. See
[`docs/bugs/2026-07-20-cortex-import-wrong-vault.md`](2026-07-20-cortex-import-wrong-vault.md).

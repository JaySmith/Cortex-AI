# Installation

## Prerequisites

- **Python 3.10+** — the distiller uses modern type-hint syntax (`str | None`)
- **git**

No other dependencies. `cortex bootstrap` creates a venv and installs everything.

## Quick Install

```bash
git clone https://github.com/JaySmith/Cortex-AI.git cortex-ai
cd cortex-ai
cortex bootstrap          # create venv + install deps
cortex install            # set up config, distiller, skill (interactive)
```

`cortex install` prompts for your **vault path** (press Enter to accept the
default — the bundled example vault). It then:

1. Creates `cortex.yaml` in `<vault>/_sync/` (if not already present)
2. Deploys the distiller scripts to `<vault>/_sync/`
3. Runs a first distillation to generate `<vault>/_sync/distilled/`
4. Installs the `cortex-ai` skill into `~/.config/opencode/skills/`

## Non-Interactive Install

Skip the prompt by passing the vault path as an argument:

```bash
cortex install /path/to/your/vault
```

This is suitable for scripts, CI, or automation.

## What Gets Installed

| Asset | Location |
|-------|----------|
| Config | `<vault>/_sync/cortex.yaml` |
| Distiller | `<vault>/_sync/distill.py`, `hive_client.py`, `cortex-import.py`, `cortex-uninstall.py` |
| Version files | `<vault>/_sync/VERSION`, `<vault>/_sync/SCHEMA_VERSION`, `<vault>/_sync/CHANGELOG.md` |
| Distilled output | `<vault>/_sync/distilled/` |
| Skill | `~/.config/opencode/skills/cortex-ai/SKILL.md` |

`cortex install` records a manifest under `<vault>/_sync/backups/` so
`cortex uninstall` can cleanly revert.

## Verifying the Install

```bash
cortex status           # checks config, vault, distilled output, skill
cortex doctor           # validates all platform integrations
cortex version          # print release + schema version
```

## Upgrading

After pulling new code:

```bash
git pull
cortex install --upgrade /path/to/your/vault
```

This backs up existing files, deploys updated distiller and skill, and
re-distills. The version guard refuses to downgrade a vault whose schema is
newer than the code.

Options:

| Flag | Effect |
|------|--------|
| `--upgrade` | Enable upgrade mode (backup-first, re-distill) |
| `--no-distill` | Skip re-distillation after deploy |
| `--dry-run` | Preview what would change without writing |

## Uninstalling

Revert all Cortex-installed assets while keeping your vault notes:

```bash
cortex uninstall --vault /path/to/your/vault --latest          # preview
cortex uninstall --vault /path/to/your/vault --latest --apply  # revert
```

Use `--purge` to also remove `<vault>/_sync/distilled/` (the generated output).
Notes in the vault are never deleted.

## Troubleshooting

### "python3 not found on PATH"

Install Python 3.10+ from [python.org](https://python.org) or your system
package manager. On macOS, `brew install python@3.12` works.

### "ERROR: vault path does not exist"

The path passed to `cortex install` does not exist. Create the vault directory
first:

```bash
mkdir -p /path/to/your/vault
cortex install /path/to/your/vault
```

### "ERROR: PyYAML is required"

The venv was not created or deps are missing. Run `cortex bootstrap` again.

### "WARNING: skill source not found"

The `skills/cortex-ai/SKILL.md` file is missing from the repo. Ensure you
cloned the full repository and are running from the repo root.

### "live vault schema is NEWER than this code"

The vault was created with a newer version of Cortex than the code you have.
Pull the latest code and try again, or accept the vault as-is:

```bash
git pull
cortex install --upgrade /path/to/your/vault
```

### Config not found by distill

If `cortex distill` can't find the config, pass it explicitly:

```bash
cortex distill --config /path/to/your/vault/_sync/cortex.yaml
```

# Quick Start (Manual Setup)

The fastest path is `cortex bootstrap` + `cortex install` from the repo root —
see the [README](../README.md). This page covers the **manual** steps and
troubleshooting if you'd rather configure things by hand or need to debug.

## 1. Install

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 2. Configure

Copy the example config into your vault's `_sync/` directory:

```bash
mkdir -p /path/to/your/vault/_sync
cp cortex.yaml.example /path/to/your/vault/_sync/cortex.yaml
```

Edit `cortex.yaml`:

```yaml
vault_path: "/path/to/your/vault"

# Where should outputs go?
targets:
  core_context:
    output_file: "/path/to/distilled/core-context.md"
  
  skills:
    skills_dir: "/path/to/.config/opencode/skills"
  
  projects:
    output_dir: "/path/to/distilled/projects"
```

Replace paths with your actual directories.

> The commands below assume `cortex.yaml` sits next to `distill.py`. If yours lives
> at `<vault>/_sync/cortex.yaml` (the default), add
> `--config /path/to/your/vault/_sync/cortex.yaml` to each `distill.py` call, or run
> `python3 distill.py --show-config` to confirm the resolved paths.

## 3. Prep Your Vault

Make sure your notes have frontmatter with `type` and `tier`:

```yaml
---
id: my-note
type: knowledge
tier: core
aliases: ["My Note Title"]
---

# My Note Content
```

(See [VAULT_SCHEMA.md](./VAULT_SCHEMA.md) for the full spec.)

## 4. Dry Run

Preview what will be written:

```bash
python3 distill.py --dry-run

# Output:
# Scanned vault: 42 notes with metadata
# --- core-context: 8 eager notes (core) ---
#   [DRY] write /path/to/core-context.md (4523 chars)
# --- skill-embeds: 12 notes -> 3 skills ---
#   [DRY] write /path/to/skills/jira/reference.md ...
# ...
```

## 5. Run

```bash
python3 distill.py

# Output:
# Scanned vault: 42 notes with metadata
# --- core-context: 8 eager notes (core) ---
#   wrote /path/to/core-context.md (4523 chars)
# --- skill-embeds: 12 notes -> 3 skills ---
#   wrote /path/to/skills/jira/reference.md ...
# ...
# Sync complete. 42 notes processed.
```

## 6. List All Notes

See what notes exist and their tiers:

```bash
python3 distill.py --list

# Output:
#   [core             ] dev-preferences           type=feedback
#   [core             ] persona                   type=feedback
#   [skill:jira      ] jira-workflow-patterns     type=knowledge
#   [skill:clarity-ppm] clarity-action-items      type=knowledge
#   [project         ] my-ai-project             type=entity
#   [vault-only      ] 2026-07-brainstorm        type=session
#   ...
```

## 7. Wire Into Agents (Optional)

If using **opencode**, the distiller can auto-wire `opencode.jsonc`:

In `cortex.yaml`:

```yaml
targets:
  core_context:
    opencode_config: "~/.config/opencode/opencode.jsonc"
```

Now when you run `distill.py`, it updates the `"instructions"` array to point to core-context.md.

## 8. Generate Portfolio (Optional)

If your vault has project notes with `tier: project` and `jira_epic` fields:

```bash
python3 gen-portfolio.py            # with live Jira status
python3 gen-portfolio.py --no-jira  # vault data only
```

Outputs `PORTFOLIO.md` in your vault root, grouped by phase (discovery | delivery | completed).

## Next Steps

- Read [VAULT_SCHEMA.md](./VAULT_SCHEMA.md) for full frontmatter reference
- Read [README.md](../README.md) for detailed configuration options
- Check out [cortex.yaml.example](../cortex.yaml.example) for all target types
- Run `distill.py --list` whenever you add notes to see them appear

## Troubleshooting

### "Config not found"

```
ERROR: Config not found: cortex.yaml
```

Make sure you copied the example into your vault's `_sync/` dir, and pass its path:
```bash
cp cortex.yaml.example /path/to/your/vault/_sync/cortex.yaml
python3 distill.py --config /path/to/your/vault/_sync/cortex.yaml
```

### "PyYAML is required"

```
ERROR: PyYAML is required.
```

Install dependencies:
```bash
.venv/bin/pip install -r requirements.txt
```

### "vault_path does not exist"

```
ERROR: vault_path does not exist: /some/path
```

Check your `cortex.yaml` — the `vault_path` must exist and point to your Obsidian vault root.

### "Note has no type"

Notes are silently skipped if they don't have a `type` field in frontmatter. Add it:

```yaml
---
id: my-note
type: knowledge    # <- add this
tier: core
---
```

### Skill directory missing

```
WARNING: skill dir missing, skipping: /path/to/skills/jira
```

The distiller found a note with `tier: skill:jira`, but `/path/to/skills/jira/` doesn't exist.

Either:
1. Create the skill directory, or
2. Change the note's tier to something else, or
3. Disable the skills target in cortex.yaml

## Regular Use

Once configured, run once before sharing or deploying:

```bash
python3 distill.py
```

Check the output into git along with your vault. The distilled files are clean, shareable, and ready for agents.

---
name: <skill-name>
description: <One-line summary of what this skill does. Include trigger phrases — when should the agent load this skill? E.g. "Use when the user says X, Y, or Z.>
---

# <Skill Name>

<1-2 sentence summary. What does this skill do? What problem does it solve?>

**MCP tools:** `<tool1>`, `<tool2>` (if applicable)
**CLI:** `<command>` (if applicable)

---

## Core Commands

### `<command1>` `<args>`

<One-line description.>

```
tool_or_cli(example="value")
```

- Key behavior or flag

### `<command2>` `<args>`

<One-line description.>

```
tool_or_cli(example="value")
```

### `<command3>` `<args>`

<One-line description.>

```
tool_or_cli(example="value")
```

---

> **For full details** on advanced commands, configuration, and reference data,
> run `<tool> --help` or read `reference.md` in this skill directory.

<!--
TEMPLATE NOTES (delete before publishing):

- Keep SKILL.md ≤ 100 lines / ≤ 700 tokens
- Each command: ≤ 10 lines
- Reference tables, configs, troubleshooting → reference.md
- Description field: ≤ 300 chars, include trigger phrases
- See docs/SKILL-PROGRESSIVE-DISCLOSURE.md for full conventions

Example descriptions:
  "Send SMS via email gateways. Use when the user says 'send a text', 'text', or 'sms'."
  "Manage homelab infrastructure — Proxmox, VLANs, Docker, TrueNAS. Use for homelab questions."
  "Work with the Cortex vault — search, add, sync notes. Use when the user says 'cortex'."
-->

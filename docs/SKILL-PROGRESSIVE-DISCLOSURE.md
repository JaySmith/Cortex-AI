# Skill Progressive Disclosure Conventions

Guidelines for writing opencode skills that minimize token load while staying
useful. Every skill loaded into context costs tokens — these conventions keep
that cost low.

## The Three-Stage Model

Skills load in three stages. Each reveals only what the agent needs to decide
whether to go deeper:

| Stage | What | Token cost | When loaded |
|-------|------|------------|-------------|
| 1. Summary | `name` + `description` from frontmatter | ~20 | Every session (in `<available_skills>`) |
| 2. Instructions | Full SKILL.md body | 100-700 | Only when `skill(name="...")` is called |
| 3. Knowledge | `reference.md` or vault notes | 500-2,000 | Only when SKILL.md tells the agent to read it |

The goal: keep stage 2 as small as possible so that loading a skill is cheap.

## Size Budget

| Target | Limit | Why |
|--------|-------|-----|
| SKILL.md lines | **≤ 100** | Keeps stage 2 under ~700 tokens |
| SKILL.md tokens | **≤ 700** | ~2-3% of a 32k context window |
| Per-command docs | **≤ 10 lines** | Forces conciseness |
| Description field | **≤ 300 chars** | Keeps stage 1 tight |

If a skill exceeds 100 lines, split the excess into reference material that the
agent reads on demand (stage 3).

## YAML Frontmatter (required)

Every SKILL.md must start with YAML frontmatter:

```yaml
---
name: <skill-name>
description: <One-line summary. Include trigger phrases for when to activate this skill.>
---
```

The `description` field is the only thing the agent sees at stage 1. Include
trigger phrases so the agent knows when to load the skill:

```yaml
description: Send SMS via email gateways. Use when the user says "send a text",
  "text", "sms", or "message".
```

## What Goes in SKILL.md

**Include:**
- 1-2 sentence summary of what the skill does
- MCP tools / CLI commands the agent will use (names only, with brief usage)
- The 3-5 most-used commands, documented concisely
- A pointer to reference.md for advanced content

**Exclude (move to reference.md or discoverable via --help):**
- Rarely-used commands
- Detailed configuration walkthroughs
- Reference tables (carrier lists, API endpoints, etc.)
- Version/changelog information
- Troubleshooting guides

## Command Documentation Style

Keep each command to **5-10 lines max**. Use this pattern:

```markdown
### `<command>` `<args>`

One-line description.

\`\`\`
tool_call(example="value")
\`\`\`

- Bullet point for key behavior or flag
```

**Bad** (25 lines):
```markdown
### sync

A sync is capture-then-rebuild-then-drain, not just a rebuild. "Sync" is the
moment to reconcile everything worth remembering from the current session into
the vault before regenerating distilled outputs — otherwise the rebuild just
re-emits stale knowledge and the session's lessons are lost.

[... 20 more lines ...]
```

**Good** (8 lines):
```markdown
### sync

Capture-then-rebuild-then-drain, in this order:

1. **Capture.** Scan session for capturable content, write each item.
2. **Rebuild.** `python3 distill.py`
3. **Drain.** Mark old logs `drained: true`, then `distill.py --purge-apply`.
```

## The Pointer Pattern

When SKILL.md references content that lives elsewhere, use a blockquote pointer:

```markdown
> **For full details** on advanced operations, run `<tool> --help` or read
> `reference.md` in this skill directory.
```

This tells the agent the content exists without loading it into context.

## Examples

### Minimal skill (persona-only, no tools)

The `homelab` skill is 17 lines — a persona definition with no commands.
This is fine. Not every skill needs commands.

### Lightweight skill (3 commands, ~40 lines)

The `sms` skill documents send/check/list and a carrier reference table.
At 41 lines it's near the limit. If it grew, the carrier table should move
to reference.md.

### Full skill (6 commands, ~117 lines)

The `cortex-ai` skill documents search/get/related/add/capture/sync with
MCP tools, paths, and a tier guide. Advanced commands (version, status,
hive, etc.) are discoverable via `distill.py --help`.

## Checklist for New Skills

- [ ] YAML frontmatter with `name` and `description` (includes trigger phrases)
- [ ] SKILL.md is ≤ 100 lines
- [ ] Each command is ≤ 10 lines
- [ ] Reference data (tables, configs, troubleshooting) is in reference.md
- [ ] Blockquote pointer to reference.md or `--help` for advanced content
- [ ] Description field is ≤ 300 chars

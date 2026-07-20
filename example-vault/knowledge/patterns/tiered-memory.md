---
id: tiered-memory
type: knowledge
tier: skill:example-skill
category: "patterns"
source: seed
updated: "2024-01-15"
aliases: ["Tiered Memory Model"]
tags: [architecture, memory, encoding]
---

# Tiered Memory Model

Notes are routed by their `tier` frontmatter so the agent only pays the token cost
for what it needs:

| Tier | Behavior | Use for |
|------|----------|---------|
| `core` | Eager — concatenated into `core-context.md`, always loaded | Preferences, personas, standing rules |
| `skill:<name>` | Lazy — embedded in `skills/<name>/reference.md` | Heavy knowledge needed only when that skill runs |
| `project` | Lazy — one file per project | Project goals, status, roadmap |
| `vault-only` | Never encoded | Session notes, drafts, logs |

This note is `tier: skill:example-skill`, so it is encoded into
`skills/example-skill/reference.md` (created for you by `cortex install`).

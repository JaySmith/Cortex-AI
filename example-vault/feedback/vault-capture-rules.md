---
id: vault-capture-rules
type: feedback
tier: core
category: "workflow"
source: seed
updated: "2024-01-15"
aliases: ["Vault Capture Rules"]
tags: [workflow, memory, mcp]
---

# Vault Capture Rules

Capture knowledge into the vault proactively during a session using the
`memory_write` MCP tool. This is how the vault stays current without hand-authoring.

## When to Capture
- The user states or corrects a **preference** → `type: feedback`, `tier: core`.
- A non-obvious **solution or pattern** is worked out → `type: knowledge`.
- A significant **decision** is made → `type: decision`.
- A **project** status changes → `type: entity`.
- The user says "remember this" / "note that" → infer type.

## The Protocol (always three steps)
1. **Search first** — `memory_search` to check for an existing note.
2. **Update if it exists** — `memory_write(..., update: true)`.
3. **Create if it doesn't** — `memory_write(...)` with full fields.

Prefer update over create; duplicate notes degrade retrieval.

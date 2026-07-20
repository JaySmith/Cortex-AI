---
name: auto-learn
description: Auto-learn from conversations — observe, propose, and capture session knowledge with human approval. Use when the user says "auto-learn", "what did you learn?", "what should I capture?", "learning mode", "learning check", or as an optional final step of a sync. Depends on the cortex-ai skill being loaded.
---

# Auto-Learn

Observe → propose → human approves → write. Three phases, no silent capture.

**Depends on:** `cortex-ai` skill (uses `cortex memory search`, `cortex memory write`).

---

## Phases

### 1. observe

Scan the current conversation and classify every substantive event as a candidate or noise.

For each candidate: run `cortex memory search "<topic>"` first. Skip if an existing note already covers it.

**Capturable signals:**

| Signal | Example |
|--------|---------|
| User correction | "No, always use async for that" |
| Repeated topic | Same pattern explained 2+ times |
| Project state change | "We moved to delivery phase" |
| Decision made | "We chose X over Y because Z" |
| Non-obvious fact | System quirk, API gotcha, tool limitation |
| Explicit "remember this" | User literally says it |

**Do NOT capture:** factual questions with no personal/project signal, one-off
commands, debugging dead-ends, or content already in an existing note.

### 2. propose

Surface a numbered list to the human. One line per candidate: the observation, and a suggested `type/tier/id`.

Example:

```text
I noticed 3 things worth capturing from this session:

[1] You prefer async/await over raw Promises in all new TS files
    → type: feedback | tier: core | id: prefer-async-await

[2] cortex encode --graph is slow on vaults >500 notes (known issue)
    → type: knowledge | tier: skill:cortex-ai | id: encode-graph-perf-note

[3] cortex v2.0.0 removed the MCP server — all ops are CLI now
    → type: knowledge | tier: skill:cortex-ai | id: cortex-v2-mcp-removal

Which to capture? (reply with numbers, e.g. "1 2" or "all" or "none")
Tier overrides? (e.g. "1 as vault-only") — defaults above apply otherwise
```

If nothing capturable was found, say so explicitly. Do **not** skip silently.

### 3. learn

Write **only** items the human approved. Per item:

1. `cortex memory search` — verify no conflicting note already exists.
2. `cortex memory write` with `--tier vault-only` — always vault-only by
   default. Only write to `core` or `skill:<name>` if the human explicitly
   overrides in the approval step.
3. Print: `Note created|updated: <id>`

Never batch-write without returning to the human if new conflicts surface mid-write.

---

## Integration with sync

Add an optional `observe → propose` step at the end of any `sync`, **after drain**.
The agent decides: "Do any captured notes warrant a learning cycle?"
If yes, run observe and propose before closing. The human decides whether to run learn.

---

> **For full candidate taxonomy, noise filters, and worked examples,**
> read `reference.md` in this skill directory.

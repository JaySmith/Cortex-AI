# auto-learn — Reference

Detailed protocol, candidate taxonomy, noise filters, and worked examples for
the auto-learn skill. Load only when the skill is invoked.

---

## Candidate taxonomy

Every observable event is classified into one of these signal types. The signal
type drives the suggested note `type` and `tier` in the proposal.

| Signal | What it looks like | Suggested type | Suggested tier | Example id |
|--------|-------------------|---------------|---------------|-----------|
| User correction | User says "no", "actually", "wrong", "instead of X use Y" | `feedback` | `core` | `prefer-async-await` |
| Repeated topic | Same concept, tool, or pattern explained 2+ times in session | `knowledge` | `skill:<name>` | `repeat-api-pattern` |
| Project state change | "We're moving to X", "Y is done", "Z is blocked" | `entity` | `project` | `project-alpha-delivery` |
| Decision made | "We chose X over Y", "let's go with Z", explicit decision | `decision` | `vault-only` | `db-choice-postgres` |
| Non-obvious fact | System quirk, workaround, limitation, gotcha | `knowledge` | `skill:<name>` | `cortex-encode-graph-perf` |
| Explicit instruction | "Remember this", "always do X", "never do Y" | `feedback` | `core` | `no-console-log-prod` |
| Workflow pattern | "I always start with...", "My process for X is..." | `knowledge` | `core` | `my-review-workflow` |

### Signal strength

Not all signals are equal. When presenting proposals, rank by confidence:

1. **High** — explicit correction or instruction ("always do X", "never do Y")
2. **Medium** — decision with stated rationale, repeated pattern
3. **Low** — single occurrence, ambiguous intent, indirect inference

Low-confidence signals can still be proposed, but mark them as such:

```text
[3] (low confidence) You mentioned using Jest over Vitest for this repo
    → type: knowledge | tier: vault-only | id: jest-preference-uncertain
```

---

## Noise filters — do NOT capture

These are the most common over-capture mistakes. Check each candidate against
this list before proposing.

| Filter | Why it fails |
|--------|-------------|
| Factual question with no personal signal | "How do I sort an array?" is not memorable |
| One-off command or flag usage | `--dry-run` once is not a pattern |
| Debugging dead-end that was discarded | Dead-ends teach the wrong lesson if stored |
| Content already in an existing note | Run `cortex memory search` first — always |
| Generic software knowledge | "TypeScript is statically typed" adds nothing |
| Temporary context that will age out | Use `expires_at` instead, or skip entirely |
| Tool output or logs | Not actionable knowledge; belongs in a log |

### The "would I search for this?" test

Before proposing a candidate, ask: if this session were next week and I
needed this information, would I search for it by this title? If no, don't
capture. This is the single most reliable filter against noise.

---

## Worked example

### Session context

A user and agent are working on a TypeScript project. The user corrects the
agent three times, a decision is made, and the session ends.

### Phase 1: observe

The agent scans the conversation and finds five events. It runs search for
each:

| # | Event | Search result | Candidate? |
|---|-------|--------------|-----------|
| 1 | "Always use async/await, never raw Promises" | No existing note | Yes |
| 2 | "We chose Postgres over SQLite for this project" | `db-choice` exists, but for a different project | Yes |
| 3 | "The MCP server was removed in v2" | `cortex-v2-mcp-removal` already exists | No (skip) |
| 4 | "Our deploy runs `npm run build` then `npm run lint`" | No existing note | Yes |
| 5 | "How do I parse YAML in Python?" | Generic question | No (noise filter) |

### Phase 2: propose

```text
I noticed 3 things worth capturing from this session:

[1] (high) You always prefer async/await over raw Promises in TS
    → type: feedback | tier: core | id: prefer-async-await

[2] (medium) Project X uses Postgres, not SQLite (rationale: concurrency)
    → type: entity | tier: project | id: project-x-uses-postgres

[3] (medium) Deploy sequence: build then lint (lint is last gate)
    → type: knowledge | tier: skill:devops | id: deploy-sequence-build-lint

Which to capture? (reply with numbers, e.g. "1 2" or "all" or "none")
Tier overrides? (e.g. "2 as project") — defaults above apply otherwise
```

### Phase 3: learn

User replies: "1 2 as core, 3"

The agent writes:

1. `cortex memory write` — `--title "prefer async/await" --type feedback
   --tier core --category workflow` with body: "Always use async/await in
   TypeScript files, never raw Promises. Corrected 2026-07-18."
2. `cortex memory write` — `--title "project-x-uses-postgres" --type entity
   --tier core --category projects` with body: "Project X uses Postgres
   (not SQLite). Chosen for concurrency support. Decision made 2026-07-18."
3. `cortex memory write` — `--title "deploy-sequence-build-lint" --type
   knowledge --tier skill:devops --category infrastructure` with body:
   "Deploy runs npm run build, then npm run lint. Lint is the final gate."

All three print `Note created: <id>` on success.

---

## Integration with sync

The auto-learn skill is designed to optionally augment a sync, not replace it.
Here is the recommended integration point:

```python
sync = {
  1. capture        ← cortex-ai skill (existing)
  2. rebuild        ← cortex encode (existing)
  3. drain          ← cortex-ai skill (existing)
  4. observe→propose ← auto-learn skill (NEW — optional, end of session)
}
```

After drain, the agent assesses whether any uncaptured learning candidates
remain. If yes, it runs `observe → propose`. The human decides whether to run
`learn`. The agent does not auto-write.

This step is **optional** — the agent should only invoke it if:

- The session was substantive (>5 meaningful turns)
- At least one high or medium confidence candidate exists
- The user has not explicitly skipped it this session

---

## Edge cases

**Contradicting an existing note:** If a proposed candidate directly contradicts
an existing `core` note, surface the conflict explicitly:

```text
⚠️  [1] conflicts with an existing core note:
    Existing: "Use Promise.all for parallel HTTP requests"
    Proposed: "Always use async/await, never Promises"

    How should this resolve? Options:
    a) Update the existing note to reflect the new preference
    b) Create the new note anyway (both will exist)
    c) Skip this candidate
```

**Multiple corrections on the same topic in one session:** Consolidate into one
proposal, not one per correction. The agent synthesizes the final state.

**User approves but with a different tier than suggested:** Respect the override
exactly. Write the note to the tier the human specified.

**No existing cortex-ai context:** If the agent cannot find
`cortex encode --show-config` or the vault is not initialized, skip the
observe phase entirely and tell the user. Do not silently capture to
unknown paths.

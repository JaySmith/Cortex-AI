"""Cortex system notes — behavior rules every vault should carry.

These are not user preferences; they are the operating contract between the
agent and the vault. They ship with every fresh vault via ``cortex init`` and
``cortex install`` (see ``_render.apply_core_notes``). Users may customize the
body after first write — apply_core_notes never overwrites an existing file.
"""


def structure() -> dict[str, str]:
    return {
        "feedback/vault-capture-rules.md": """\
---
id: vault-capture-rules
type: feedback
tier: core
aliases: ["Vault Capture Rules"]
category: "workflow"
updated: "2026-09-08"
---

The Cortex vault is agent-driven: capture proactively during every session, don't
wait to be asked. Writes go through `cortex memory write` (auto-encodes).

## Capture Events — the five things worth remembering

| Event | Capture when… | Type |
|-------|---------------|------|
| **Goal** | What we're trying to achieve changed/clarified | `entity` |
| **Plan/State** | The path or current status changed | `entity` |
| **Knowledge** | Something non-obvious was worked out | `knowledge` |
| **Risk** | Something that might block success was found | `risk` |
| **Decision** | A commitment was made (with reasoning) | `decision` |

Two always-honour sources alongside the five:
- User states/corrects a preference/working-style/rule → `feedback`, tier `core`.
- User says "remember/save/note this" → capture as the fitting type.

## When to scan (cadence)

Criteria need a trigger. Run the five-event scan — unasked — at these checkpoints:
task/todo completes · a decision is reached · a preference is stated/corrected ·
a non-obvious problem is solved · a risk is identified · before handoff/sync/end
of a substantive session. If nothing clears the Meaningful Bar, do nothing.

## The Meaningful Bar

Capture only what's **durable** — useful to a *future* session. Tiebreaker:
> If a fresh agent started cold next week, would *not* having this note make it
> repeat work, break a stated preference, or lose context? Yes → capture. No →
> skip. Unsure → capture as `vault-only` (cheap, prunable).

At handoff, if ≥1 event fired, write one `session` note (`vault-only`). Handoff
after only Q&A/scratch = not meaningful → skip the session note.

## Do NOT capture

Pure Q&A · restatement of an existing note (search first — no-op = skip) ·
scratch/transient output · speculation ("maybe later") · self-evident behaviour ·
conversational noise.

## Protocol (three steps)

> For general information retrieval (not just writes), see [[vault-retrieval-priority]].

1. **Search** — `cortex memory search "<query>"` for an existing note.
2. **Update** if it exists — `cortex memory write ... --update`.
3. **Create** if not. (Prefer update — duplicates degrade retrieval.)

## Types & tiers

- `risk`: `project` if it threatens one project, `core` if standing. Searchable.
- `entity`: Goal and Plan/State (a project's phase/goals/status).
- `decision`/`knowledge`: tiered by reach (`vault-only`/`project`/`skill:<x>`/`core`).

## Operational

- **Proactive** — capture on event fire; standing permission already granted.
- **Visible** — surface autonomous captures in one line: `Captured: <id>
  (<created|updated>) — <why>`. Batch into a short list, not a report.
- **Session summary** — at handoff/end, one prose `session` note (`vault-only`):
  work done, decisions, risks, follow-ups. Skip if nothing meaningful.

## Related
- vault-retrieval-priority — general search-first retrieval order
- workflow-rules — other behavioral rules
""",
        "feedback/vault-retrieval-priority.md": """\
---
id: vault-retrieval-priority
type: feedback
tier: core
category: "workflow"
aliases: ["Vault Retrieval Priority", "Vault First Rule"]
updated: "2026-09-08"
---

Before reaching for any external source — file search, web search, a skill's
reference doc, or a tool — search the vault first.

## The rule

1. **Vault first** — `cortex memory search "<query>"` for any factual question
   about projects, preferences, patterns, decisions, people, or systems.
2. **Fall through** — if the vault returns nothing useful, proceed to the normal
   source (files, web, skill, tool). Surface the miss only when it's substantive
   (non-trivial topic, or the vault was the obvious place to look):
   "Nothing in the vault on X — checking [source]." Skip the callout for
   routine/incidental lookups.
3. **Write-guard** — before any `cortex memory write`, search first. Update if a
   note exists; create only if not. (See vault-capture-rules for full write protocol.)

## What "search first" covers

- Project status, phase, goals, roadmap questions
- Jay's preferences, working-style rules, standing decisions
- Known patterns, API quirks, system facts (Jira, Clarity, SharePoint, etc.)
- People, teams, accountIds, system connections
- Anything that might have been captured in a prior session

## What it does NOT replace

- Grep/Glob/Read for code search within a repo (vault doesn't index code)
- Tool-specific operations (git, npm, pytest, etc.)
- Live/real-time data (current sprint board, live Jira issue status)

## Related
- vault-capture-rules — write protocol (search → update → create)
"""
    }
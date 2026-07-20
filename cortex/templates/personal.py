"""Personal vault template."""


def structure() -> dict[str, str]:
    return {
        "feedback/preferences.md": """\
---
id: preferences
type: feedback
tier: core
aliases: ["Personal Preferences"]
updated: "2026-07-20"
---

# Personal Preferences

Add your standing preferences here. These are always loaded by your agent.

## Communication Style

- Be direct and concise
- Show code examples over long explanations
- Skip pleasantries, get to the point

## Work Hours

<!-- Add your typical schedule so the agent knows when to expect you -->

## Tools

<!-- List your go-to tools, editors, CLIs -->
""",
        "feedback/working-style.md": """\
---
id: working-style
type: feedback
tier: core
aliases: ["Working Style"]
updated: "2026-07-20"
---

# Working Style

How you like to work. Your agent reads this every session.

## Decision Making

- Prefer small, reversible decisions
- Write things down before committing

## Review Process

<!-- How do you like feedback on your work? -->
""",
        "entities/projects/example-project.md": """\
---
id: example-project
type: entity
tier: project
aliases: ["Example Project"]
category: "Active"
updated: "2026-07-20"
---

# Example Project

Replace this with an actual project note.

## Goals

- [ ] Goal 1
- [ ] Goal 2

## Status

Not started.

## Notes

<!-- Free-form context the agent should know about this project -->
""",
        "decisions/decisions-log.md": """\
---
id: decisions-log
type: knowledge
tier: vault-only
aliases: ["Decisions Log"]
tags: [decisions]
updated: "2026-07-20"
---

# Decisions Log

Record significant decisions here. This note stays private (vault-only).

## Template

### [Date] Decision Title

**Context:** Why this decision was needed.
**Decision:** What was decided.
**Alternatives considered:** What else was on the table.
**Consequences:** What this means going forward.
""",
    }

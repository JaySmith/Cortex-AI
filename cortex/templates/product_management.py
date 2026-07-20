"""Product Management vault template."""


def structure() -> dict[str, str]:
    return {
        "feedback/pm-preferences.md": """\
---
id: pm-preferences
type: feedback
tier: core
aliases: ["PM Preferences"]
updated: "2026-07-20"
---

# Product Management Preferences

Standing rules for product work.

## Prioritization

- Impact over effort
- User-facing over internal
- Reversible over irreversible

## Communication

- Lead with the "so what"
- Use data, not opinions
- Keep stakeholder updates concise
""",
        "knowledge/roadmap-template.md": """\
---
id: roadmap-template
type: knowledge
tier: skill:team-status
category: "Templates"
aliases: ["Roadmap Template"]
updated: "2026-07-20"
---

# Roadmap Template

Use this structure for project roadmaps.

## Q3 2026

| Initiative | Status | Owner | Notes |
|------------|--------|-------|-------|
| Initiative 1 | On track | | |
| Initiative 2 | At risk | | |
| Initiative 3 | Not started | | |

## Key Dates

- **YYYY-MM-DD:** Milestone 1
- **YYYY-MM-DD:** Milestone 2
""",
        "entities/projects/example-initiative.md": """\
---
id: example-initiative
type: entity
tier: project
aliases: ["Example Initiative"]
category: "Discovery"
updated: "2026-07-20"
---

# Example Initiative

Replace with your actual initiative.

## Problem Statement

<!-- What user problem does this solve? -->

## Success Metrics

- Metric 1: target
- Metric 2: target

## Requirements

- [ ] Requirement 1
- [ ] Requirement 2

## Timeline

<!-- Expected delivery dates -->
""",
        "decisions/product-decisions.md": """\
---
id: product-decisions
type: knowledge
tier: vault-only
aliases: ["Product Decisions"]
tags: [decisions, product]
updated: "2026-07-20"
---

# Product Decisions Log

Record product decisions here. This note stays private (vault-only).

## Template

### [Date] Decision Title

**Context:** What prompted this decision.
**Options:** What was on the table.
**Decision:** What was chosen and why.
**Impact:** What changes as a result.
""",
    }

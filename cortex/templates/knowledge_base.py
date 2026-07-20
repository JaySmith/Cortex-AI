"""Knowledge Base vault template."""


def structure() -> dict[str, str]:
    return {
        "feedback/kb-preferences.md": """\
---
id: kb-preferences
type: feedback
tier: core
aliases: ["KB Preferences"]
updated: "2026-07-20"
---

# Knowledge Base Preferences

How you want your knowledge base organized.

## Structure

- One topic per note
- Use tags for cross-cutting concerns
- Keep notes focused and scannable

## Maintenance

- Review quarterly
- Archive outdated notes (tag: archived)
- Promote frequently-used notes to skill tiers
""",
        "knowledge/reference/template-note.md": """\
---
id: template-note
type: knowledge
tier: core
category: "Reference"
aliases: ["Template Note"]
tags: [template]
updated: "2026-07-20"
---

# Template Note

Copy this structure for new knowledge notes.

## Section 1

<!-- Content here -->

## Section 2

<!-- Content here -->

## Related Notes

- [[other-note]]
""",
        "entities/topics/example-topic.md": """\
---
id: example-topic
type: entity
tier: project
aliases: ["Example Topic"]
category: "Reference"
updated: "2026-07-20"
---

# Example Topic

A top-level topic in your knowledge base.

## Overview

<!-- What is this topic about? -->

## Key Concepts

- Concept 1: brief explanation
- Concept 2: brief explanation

## Resources

- [Link text](url)
""",
        "decisions/kb-structure.md": """\
---
id: kb-structure
type: knowledge
tier: vault-only
aliases: ["KB Structure Decisions"]
tags: [meta, decisions]
updated: "2026-07-20"
---

# Knowledge Base Structure Decisions

How the KB is organized and why. This note stays private (vault-only).

## Directory Layout

- `knowledge/` — reference material and procedures
- `entities/` — topics and concepts
- `feedback/` — preferences and style rules
- `decisions/` — records of choices made

## Tagging Conventions

<!-- Your tagging rules here -->
""",
    }

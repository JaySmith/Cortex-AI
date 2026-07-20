"""Engineering vault template."""


def structure() -> dict[str, str]:
    return {
        "feedback/dev-preferences.md": """\
---
id: dev-preferences
type: feedback
tier: core
aliases: ["Developer Preferences"]
updated: "2026-07-20"
---

# Developer Preferences

Standing rules for code and tooling.

## Default Stack

- TypeScript with strict mode
- ESM imports, async/await
- Node.js runtime

## Code Style

- Keep APIs small and composable
- Ship the thinnest viable abstraction
- Tests before merge

## Git

- Conventional commits: feat:, fix:, chore:, docs:, refactor:, test:
- One concern per PR
""",
        "feedback/code-review-style.md": """\
---
id: code-review-style
type: feedback
tier: core
aliases: ["Code Review Style"]
updated: "2026-07-20"
---

# Code Review Style

How you want code reviewed.

## Priorities

1. Correctness first
2. Then readability
3. Then performance

## pet Peeves

- Premature abstraction
- Magic numbers without names
- Tests that only test the happy path
""",
        "knowledge/patterns/api-design.md": """\
---
id: api-design-patterns
type: knowledge
tier: skill:codebase-design
category: "Patterns"
aliases: ["API Design Patterns"]
updated: "2026-07-20"
---

# API Design Patterns

Reference patterns for designing clean APIs.

## Rule of Least Surprise

- Methods do what their name says
- No hidden side effects
- Errors are explicit, not swallowed

## Composition over Inheritance

- Small functions that do one thing
- Wire them together at the call site
- Avoid deep class hierarchies

## Error Handling

- Return structured errors, not strings
- Distinguish between expected and unexpected failures
- Let callers decide how to handle
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

Replace with your actual project.

## Tech Stack

<!-- What technologies does this project use? -->

## Architecture

<!-- High-level architecture notes -->

## Goals

- [ ] Goal 1
- [ ] Goal 2

## Gotchas

<!-- Things that will bite you if you forget them -->
""",
        "decisions/architecture-decisions.md": """\
---
id: architecture-decisions
type: knowledge
tier: vault-only
aliases: ["Architecture Decisions"]
tags: [adr, architecture]
updated: "2026-07-20"
---

# Architecture Decision Records

Keep ADRs here. This note stays private (vault-only).

## Template

### ADR-NNN: Title

**Status:** Proposed | Accepted | Deprecated | Superseded by ADR-XXX

**Context:** What is the issue that motivates this decision?

**Decision:** What is the change that is being proposed or has been agreed upon?

**Consequences:** What becomes easier or more difficult to do because of this change?
""",
    }

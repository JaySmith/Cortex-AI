# Memory Model

Cortex is a persistent, tiered memory system for AI agents. Notes live in a
plain-Markdown vault. An encoding pipeline reads every note and routes it
to the right output based on its **tier** — so the agent loads only what it
needs, when it needs it.

## Core Concepts

### The Vault

An Obsidian-style directory of Markdown notes, each with YAML frontmatter.
Notes are grouped by what they describe:

```
your-vault/
├── feedback/       ← preferences, persona, standing rules
├── knowledge/      ← reference docs, patterns, procedures
├── entities/       ← projects, people, systems, teams
├── decisions/      ← records of choices
└── logs/           ← session and event notes
```

### Note Types

Every note declares a `type` in its frontmatter:

| Type | Purpose |
|------|---------|
| `knowledge` | Patterns, reference material, how-tos |
| `entity` | Projects, people, systems, data structures |
| `feedback` | User preferences, persona, working style |
| `decision` | Records of choices with reasoning |
| `session` | Transient conversation summaries |
| `log` | Session logs, event trails |

Notes without a `type` are skipped entirely.

### The Tier System

Every note declares a `tier` that controls when it reaches the agent:

| Tier | When Loaded | Output Target |
|------|-------------|---------------|
| `core` | Every conversation, unconditionally | `core-context.md` |
| `skill:<name>` | Only when that skill is invoked | `skills/<name>/reference.md` |
| `project` | On demand, when the project comes up | `projects/<id>.md` |
| `vault-only` | Never | Nothing (stays in vault only) |

**Core** keeps the always-loaded footprint small — standing preferences,
persona, rules. **Skill** and **project** tiers load lazily on demand.
**Vault-only** keeps drafts, session notes, and research private.

The always-loaded context also includes a lightweight **pointer index** —
a table of contents that tells the agent what skill and project notes exist,
without loading their content. This lets the agent reason about available
knowledge and pull in detail when relevant.

### Encoding

The encoder (`cortex/encoder/core.py`, invoked via `cortex encode`) reads every note
in the vault and routes it to output targets based on tier:

```
vault notes
  → scan & parse frontmatter
  → tier routing:
      core            → core-context.md (eager, always loaded)
      skill:jira      → skills/jira/reference.md (lazy)
      skill:clarity   → skills/clarity-ppm/reference.md (lazy)
      project         → projects/<id>.md (lazy)
      vault-only      → skip
  → write changed outputs (idempotent — only writes diff)
```

No database, no cloud service, no background daemon. Files in, files out.

### Capture-Then-Rebuild

The everyday workflow is **capture first, rebuild second**:

1. **Capture** — the agent writes notes into the vault during conversation
   (preferences, decisions, patterns, session summaries) using
   `cortex memory write`. Individual writes trigger an automatic rebuild in
   the background (unless `--no-encode` is passed).
2. **Rebuild** — `cortex encode` regenerates all encoded outputs from the
   current vault state. This is the explicit step you run after a batch of
   manual edits.

A "sync" is this two-step process. The rebuild without capture is just a
rebuild — it re-emits what's already there. The capture without a rebuild
leaves the encoded outputs stale.

## Scoring

Search ranks notes by weighted matches across the note's id, aliases, tags,
category, and body. Id and alias hits score highest; body matches score
lowest. Related-note scoring weights shared tags most heavily, then category,
then type. The scoring is deliberately simple and explainable — you can
predict what will come back.

## Vault-Only Notes

`vault-only` is a deliberate feature. A note in this tier can be written by
the agent but is never encoded back into its context. This gives you:

- **Signal filtering** — the agent captures observations without them
  becoming established fact on the next turn. You review and promote the
  solid ones.
- **A private workspace** — half-formed thinking stays yours.
- **An audit trail** — if the agent records something wrong, you can see it
  and correct the source.
- **Zero context cost** — the agent can be proactive about capture without
  bloating the always-loaded budget.

`session` and `log` note types default to this tier. Promote a note later by
changing its `tier` and re-encoding.

## Versioning

Cortex tracks two independent numbers:

| Number | File | Meaning |
|--------|------|---------|
| Release version (SemVer) | `VERSION` | Which release of the toolchain |
| Schema version (integer) | `SCHEMA_VERSION` | The on-disk data contract |

Every encode run compares the code's schema version against the vault's. If
the vault is newer, the encoder refuses to run (no silent downgrades). If
the code is newer, it auto-migrates (backing up first). Check status with
`cortex encode --check` or `cortex status`.

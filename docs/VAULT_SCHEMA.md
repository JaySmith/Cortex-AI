# Cortex Vault Schema

How to structure your Obsidian vault for distillation.

> **For the canonical data model** (field definitions, types, hub value format),
> see [`VAULT-NOTE-SCHEMA.md`](VAULT-NOTE-SCHEMA.md). This file covers directory
> layout and frontmatter usage; that file covers the wire format.

## Directory Layout

```
your-vault/
├── _sync/                          (distiller lives here + config)
│   ├── distill.py                 
│   ├── gen-portfolio.py           
│   ├── cortex.yaml                (edit this)
│   └── distilled/                 (generated output)
│
├── feedback/                       (tier: core — always eager)
│   ├── permissions.md
│   ├── persona.md
│   ├── dev-preferences.md
│   └── ...
│
├── knowledge/                      (mixed tiers)
│   ├── patterns/
│   │   ├── jira-workflow-*.md     (tier: skill:jira)
│   │   ├── clarity-action-item-*.md (tier: skill:clarity-ppm)
│   │   └── ...
│   │
│   ├── calendars/
│   │   └── sprint-fiscal-*.md     (tier: skill:sprint-calendar)
│   │
│   └── api/
│       └── product-categories.md   (tier: skill:aie-artifact-audit)
│
├── entities/
│   └── projects/
│       ├── my-ai-project.md        (tier: project)
│       ├── another-initiative.md   (tier: project)
│       └── ...
│
├── decisions/                      (tier: vault-only or skill:*)
│   ├── 2026-05-*.md
│   └── ...
│
├── logs/                           (tier: vault-only)
│   └── 2026-07-*.md
│
└── templates/                      (skipped by scanner)
    ├── project-template.md
    └── ...
```

## Frontmatter Reference

Every note that should be distilled **must** have YAML frontmatter:

```yaml
---
id: unique-note-slug
type: knowledge | entity | feedback | log | session | custom
tier: core | skill:skillname | project | vault-only
category: optional-category (e.g., "API Reference")
tags: [optional, list, of, tags]
aliases: ["Human Readable Title"]
updated: "2024-01-15"
---
```

### `id` (required for distillation)

- Must be unique across the vault
- Used as the filename in output (e.g., `my-api.md`)
- Defaults to the file's stem if omitted, but best to be explicit
- Example: `jira-workflow-patterns`

### `type` (required)

Notes without a `type` are skipped entirely.

| Type | Purpose | Distilled? |
|------|---------|-----------|
| `knowledge` | Patterns, docs, reference material | Yes, if tier allows |
| `entity` | Data structures, schema definitions, catalogs | Yes, if tier allows |
| `feedback` | Standing preferences, persona, permissions | Yes, if tier allows |
| `log` | Session logs, incident logs | No (vault-only) |
| `session` | Transient conversation notes | No (vault-only) |
| Custom | Any string; used for filtering | Yes, if tier allows |

### `tier` (required)

Routes the note to specific output targets:

| Tier | Behavior | Distilled Into |
|------|----------|---|
| `core` | Eager: concatenated into core-context.md on every sync | core-context.md |
| `skill:name` | Lazy: embedded into `skills/name/reference.md` | skill reference.md |
| `project` | Lazy: individual project file in `projects/` | projects/*.md |
| `vault-only` | Never distilled; stays in Obsidian only | — |

Examples:
- `tier: core` → Always loaded for agents
- `tier: skill:jira` → Loaded only when the jira skill is invoked
- `tier: project` → Individual project context file
- `tier: vault-only` → Research, drafts, personal notes

### `category` (optional)

A grouping label for organization. Used in some output formats but not enforced.

Examples: `API Reference`, `Workflow Patterns`, `Hardware Diagnostics`

### `tags` (optional)

List of tags for filtering. Some tags have special meaning:

- `draft` → excluded from distillation (configurable)
- `archived` → excluded from distillation (configurable)
- `session-only` → excluded from distillation (configurable)
- Custom tags → filtered by config in `exclude_tags` section

### `aliases` (optional)

List of human-readable titles. Used for display (e.g., section headings in distilled output).
If absent, the title is derived from the `id` (slug → Title Case).

```yaml
aliases: ["Jira Workflow Patterns", "How Jira Workflows Work"]
```

The first alias is the primary title.

### `updated` (optional)

ISO date when this note was last updated. Used for change tracking and freshness signals.

```yaml
updated: "2024-07-10"
```

## Tier Examples

### Core Notes (tier: core)

Always loaded. Use for standing preferences, persona, permissions, default behaviors.

```yaml
---
id: dev-preferences
type: feedback
tier: core
aliases: ["Developer Preferences"]
updated: "2026-07-10"
---

## Default Stack

Node.js + TypeScript, ESM, strict mode.

...
```

### Skill Notes (tier: skill:name)

Heavy reference material that's only needed when a skill loads. Keeps core-context lean.

```yaml
---
id: jira-workflow-patterns
type: knowledge
tier: skill:jira
category: "Workflow Patterns"
aliases: ["Jira Workflow Patterns"]
updated: "2026-07-10"
---

## Transition Rules

When moving between statuses, check...

...
```

### Project Notes (tier: project)

Project-specific context: goals, roadmap, status, artifacts.

```yaml
---
id: my-ai-project
type: entity
tier: project
category: "Active Delivery"
aliases: ["My AI Project"]
jira_epic: "AIE-123"
phase: delivery
sharepoint_folder: "My AI Project"
updated: "2026-07-10"
---

## Goals

- [ ] Goal 1
- [ ] Goal 2

## Roadmap

| Milestone | Target | Notes |
|-----------|--------|-------|
| Phase 1 | 2026-Q3 | Setup & discovery |
| Phase 2 | 2026-Q4 | Delivery |

...
```

### Vault-Only Notes (tier: vault-only)

Research, drafts, session notes that never leave Obsidian.

```yaml
---
id: 2026-07-brainstorm-xyz
type: session
tier: vault-only
tags: [brainstorm, exploratory]
updated: "2026-07-10"
---

# Quick thoughts on XYZ

...
```

#### Why write notes the agent can never read?

`vault-only` is a deliberate feature, not a dead end. A note in this tier can be
**written by the assistant but is never distilled back into its context** — the
assistant can capture it, but can't read it on a later turn. That one-way flow
gives you four things:

- **Signal filtering without a feedback loop.** The assistant proposes what it
  learns — a pattern it spotted, a hunch, a session observation. If that went
  straight into the always-on context, the assistant would treat its own
  unvalidated guess as established fact next turn. Landing it in `vault-only`
  instead means *you* review it in Obsidian, refine or discard it, and only
  **promote** the solid ones to `core` / `skill:*` / `project`. Curation happens
  before knowledge becomes standing context.
- **A private workspace.** Half-formed thinking, brainstorms, and decisions
  you're still working through stay yours. The assistant sees the clean
  conclusion once you finalize it — not the messy draft.
- **An audit trail.** If the assistant records something wrong, you can see it
  and trace *why* it thought so, then correct the source. Its reasoning stays
  visible and fixable.
- **Zero context cost.** The assistant can be proactive and noisy about capture
  without bloating the always-loaded budget — none of it is paid for at
  inference time until you promote it.

`session` and `log` note types default to this tier automatically. To promote a
note later, just change its `tier` and re-distill.

## Special Frontmatter (Optional)

Some notes support extra fields for specific features:

- `jira_epic` → used by `gen-portfolio.py` to fetch live status
- `phase` → used by `gen-portfolio.py` to group projects (discovery | delivery | completed)
- `personal` → marks a project as personal (portfolio display only)
- `sharepoint_folder` → SharePoint path for artifact links (portfolio display)
- `sharepoint_roadmap` → filename of roadmap in SharePoint (portfolio display)
- `agents` → list of agent platforms a note is scoped to. **Parsed but not yet
  used for routing** — reserved for future multi-platform filtering (see the
  "multi-platform agent routing" item in `ROADMAP.md`). Safe to omit.
- `hive` → controls sync to shared vault (cortex-hub). Three states:
  - `true` — always sync to hub, even if tier is not in `replicate_tiers`
  - `false` — never sync, even if tier is in `replicate_tiers`
  - omit — use `replicate_tiers` from config (default behavior)

## Exclusion Rules

Notes are excluded from distillation if:

1. **No `type` field** → entirely skipped
2. **tier: vault-only** → explicitly excluded
3. **note_type in vault_only_types** → excluded (default: session, log)
4. **tags contain exclude_tags** → excluded (default: draft, archived, session-only)
5. **Missing output target** → e.g., tier:skill:unknown skipped if skills target disabled

## Wiki Links

By default, distill.py strips Obsidian wiki links:

- `[[foo|bar]]` → `bar`
- `[[page-title]]` → `page-title`

Disable with `strip_wiki_links: false` in cortex.yaml.

## Best Practices

1. **Use slug-style IDs**: `my-project`, `jira-workflow-patterns`, `sprint-calendar`
2. **Clear tier assignment**: every note either core, skill:*, project, or vault-only
3. **Meaningful aliases**: first alias becomes the section title in output
4. **Group by type + directory**: knowledge/ for patterns, entities/ for data, feedback/ for preferences
5. **Tag strategically**: use tags for filtering or metadata, not for tier (tier is frontmatter)
6. **Keep core lean**: only standing preferences in core; heavy docs go in skill: tiers
7. **Project metadata**: include jira_epic, phase, sharepoint_folder for portfolio generation

## Lint & Validation

No built-in linting yet, but good habits:

- Run `distill.py --list` to see all notes + tiers
- Run `distill.py --dry-run` before syncing
- Check `_sync/last-sync.json` for state tracking

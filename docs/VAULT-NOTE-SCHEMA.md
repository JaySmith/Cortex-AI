# Vault Note Schema

Canonical definition of a vault note's data model. Both cortex-ai and
cortex-hub reference this document. If you change the data model, update
this file first, then propagate to implementation.

## Fields

| Field | Type | Required | Source | Description |
|-------|------|----------|--------|-------------|
| `id` | string | yes | frontmatter | Unique slug (e.g. `my-project`, `jira-workflow-patterns`) |
| `type` | string | yes | frontmatter | `knowledge` \| `entity` \| `feedback` \| `log` \| `session` \| custom |
| `tier` | string | yes | frontmatter | `core` \| `skill:name` \| `project` \| `vault-only` |
| `category` | string | no | frontmatter | Grouping label (e.g. `API Reference`, `Workflow Patterns`) |
| `tags` | string[] | no | frontmatter | Filter tags for search and exclusion |
| `aliases` | string[] | no | frontmatter | Human-readable titles (first = primary) |
| `updated` | string | no | frontmatter | ISO date `YYYY-MM-DD` — used for conflict resolution |
| `content` | string | no | body | Note body (markdown), extracted at push time |
| `machine_id` | string | yes (hub) | runtime | Origin machine ID, added at push time |

## Representations

A vault note exists in three forms: as a file on disk, as a JSON value
in the hub, and as a key in the hub's memory store.

### 1. Vault File (Obsidian)

YAML frontmatter + markdown body. This is the source of truth.

```yaml
---
id: my-project
type: entity
tier: project
category: "Active Delivery"
tags: [ai, infrastructure]
aliases: ["My AI Project"]
updated: "2026-07-10"
---

## Goals

- [ ] Goal 1
- [ ] Goal 2
```

### 2. Hub Value (JSON)

JSON string stored via `hub_memory_set`. The `content` field is the
markdown body with wiki-links stripped and H1 dropped.

```json
{
  "id": "my-project",
  "type": "entity",
  "category": "Active Delivery",
  "tier": "project",
  "tags": ["ai", "infrastructure"],
  "aliases": ["My AI Project"],
  "updated": "2026-07-10",
  "content": "## Goals\n\n- [ ] Goal 1\n- [ ] Goal 2",
  "machine_id": "office-desktop"
}
```

### 3. Hub Key Format

```
vault/{machine_id}/{note_id}
```

Examples:
- `vault/office-desktop/my-project`
- `vault/laptop/jira-workflow-patterns`

### 4. Hub Tags

Tags stored alongside the memory entry for filtering:

```
["vault", "{machine_id}", "{tier}", "{type}"]
```

Example:
```
["vault", "office-desktop", "project", "entity"]
```

## Field Mapping

| Vault Frontmatter | Hub JSON Field | Notes |
|-------------------|----------------|-------|
| `id` (filename stem) | `id` | Same value |
| `type` | `type` | Same value |
| `tier` | `tier` | Same value |
| `category` | `category` | Same value |
| `tags` | `tags` | Same value |
| `aliases` | `aliases` | Same value |
| `updated` | `updated` | Same value |
| (body) | `content` | Extracted, wiki-links stripped, H1 dropped |
| — | `machine_id` | Added at push time |

## Conflict Resolution

When the same note exists on multiple machines, **newest `updated`
timestamp wins**. This is a simple, predictable rule for v1.

Future: section-aware merge (compare individual sections, not the
whole file). Deferred — the failure mode is rare with curated notes.

## Exclusion Rules

Notes are excluded from hub sync if:

1. `hive: false` in frontmatter — never sync
2. `tier: vault-only` and not in `replicate_tiers` — excluded by default
3. `hive` omitted — use `replicate_tiers` from `cortex.yaml` config

See `hive_eligible()` in `distill.py` for the exact logic.

## Version History

| Schema Version | Changes |
|----------------|---------|
| v2 (current) | Added `hive` frontmatter field, `machine_id` in hub value |
| v1 | Initial schema |

# Example Vault

A minimal starter vault so the encoder works the moment you clone the repo.
It has one note per tier:

| File | Tier | What it demonstrates |
|------|------|----------------------|
| `feedback/dev-preferences.md` | `core` | Eager note → `core-context.md` |
| `feedback/vault-capture-rules.md` | `core` | Eager note (the agent's capture protocol) |
| `knowledge/patterns/tiered-memory.md` | `skill:example-skill` | Lazy skill embed |
| `entities/projects/example-project.md` | `project` | Per-project context file |
| `logs/2024-01-15-session.md` | `vault-only` | Skipped (Obsidian-only) |

The directory layout (`feedback/`, `knowledge/patterns/`, `entities/projects/`,
`logs/`) matches what the MCP `memory_write` tool expects, so agent-driven capture
writes land in the right place. Note: project **phase** (`delivery`/`discovery`/
`completed`) is a frontmatter attribute, not a subfolder — project notes live flat
in `entities/projects/`.

Run `cortex install` from the repo root to encode this vault and see the output in
`example-vault/_sync/encoded/`.

Once you understand the flow, run `cortex install` against your own vault. It
generates a `cortex.yaml` at `<vault>/_sync/cortex.yaml` pointing at your paths.

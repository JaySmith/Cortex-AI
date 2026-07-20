# Cortex

Persistent, tiered memory for AI coding agents. Notes live in an
Obsidian-style vault; Cortex encodes them into agent-consumable files so
your agent shows up to every conversation already knowing your preferences,
patterns, and projects.

```
Build   (vault -> agent):  notes  -> cortex encode  -> core-context.md + memory.json
Capture (agent -> vault):  agent  -> cortex memory write  -> note written -> encode (auto)
```

## Install

Requires **Python 3.10+** and [uv](https://docs.astral.sh/uv/).

```bash
# 1. Install the CLI tool (one-time)
uv tool install git+https://github.com/JaySmith/Cortex-AI.git

# 2. Set up a vault
cortex install ~/cortex-ai
```

`cortex install` creates a config, installs the skill, and runs the first
encode. For non-interactive installs:

```bash
cortex install /path/to/your/vault
```

To update after a new release:

```bash
# 1. Update the CLI
uv tool install --reinstall git+https://github.com/JaySmith/Cortex-AI.git

# 2. Update vault assets (skill + re-encode)
cortex install --upgrade
```

## Quick Start

```bash
cortex status                                    # verify install
cortex memory list                               # see all notes with type, tier
cortex memory write --title "My Stack" --type feedback --tier core
cortex encode                                    # rebuild output
cortex memory search "stack"                     # search memory
```

## Common Commands

| Command | What it does |
|---------|-------------|
| `cortex install [vault]` | Set up Cortex for a vault |
| `cortex install --upgrade` | Upgrade an existing install |
| `cortex uninstall --vault <v>` | Revert installed assets (notes kept) |
| `cortex encode` | Rebuild all encoded output |
| `cortex encode --dry-run` | Preview without writing |
| `cortex encode --check` | Version/schema health check |
| `cortex status` | Installation health |
| `cortex doctor` | Validate all platform integrations |
| `cortex memory search <q>` | Search encoded memory |
| `cortex memory get <id>` | Fetch a single note by id |
| `cortex memory list` | List all notes (filter by `--tier`, `--type`) |
| `cortex memory write` | Create or update a vault note |
| `cortex import` | Import existing agent context |
| `cortex version` | Print version info |

## How Memory Works

Each note declares a **tier** that controls when it reaches your agent:

| Tier | Behavior | Use for |
|------|----------|---------|
| `core` | Eager — always loaded | Preferences, personas, standing rules |
| `skill:<name>` | Lazy — loaded only when that skill runs | Heavy reference docs, checklists |
| `project` | Lazy — loaded on demand | Project goals, status, roadmap |
| `vault-only` | Never encoded | Session notes, drafts, research |

The always-loaded context also includes a **pointer index** — a table of
contents telling the agent what skill and project notes exist without loading
their content. See [docs/memory-model.md](docs/memory-model.md) for full
detail.

## CLI Memory Commands

The `cortex` CLI provides these commands for mid-conversation memory operations:

| Command | Kind | Does |
|---------|------|------|
| `cortex memory search <q>` | read | Keyword search across encoded notes |
| `cortex memory get <id>`  | read | Fetch one note by id |
| `cortex memory list`      | read | Table of all notes (filter by `--tier`, `--type`) |
| `cortex memory write`     | write | Create/update a note, then auto-encode |

## Supported Agents

| Agent | Status | Install |
|-------|--------|---------|
| opencode | Supported | `cortex opencode install` |
| codex | Stub | `cortex codex install` |
| copilot | Stub | `cortex copilot install` |

## Repo Layout

```
VERSION                    Release version (SemVer)
SCHEMA_VERSION             On-disk data contract version
CHANGELOG.md               Release history + versioning rules
ROADMAP.md                 Planned direction
cortex/                    Python package (CLI, encoder, platforms)
skills/cortex-ai/          opencode skill template
example-vault/             Starter vault — one note per tier
docs/                      overview, QUICKSTART, CLI reference, etc.
```

## Docs

- [docs/overview.md](docs/overview.md) — what Cortex is and how it works
- [docs/installation.md](docs/installation.md) — installation guide
- [docs/cli-reference.md](docs/cli-reference.md) — CLI reference
- [docs/memory-model.md](docs/memory-model.md) — tier system, note types, encoding
- [docs/QUICKSTART.md](docs/QUICKSTART.md) — minimal productive path
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — contributing: dev setup, dev loop, releasing
- [docs/troubleshooting.md](docs/troubleshooting.md) — common issues and fixes
- [docs/migration.md](docs/migration.md) — schema version migration procedures
- [docs/VAULT_SCHEMA.md](docs/VAULT_SCHEMA.md) — frontmatter reference
- [docs/EXTENDING.md](docs/EXTENDING.md) — add custom output targets
- [ROADMAP.md](ROADMAP.md) — planned direction for future releases

## Related

- **[Cortex-Hub](https://github.com/JaySmith/Cortex-Hub)** — Multi-agent
  coordination layer. Shared memory and messaging for AI agents.

## License

MIT.

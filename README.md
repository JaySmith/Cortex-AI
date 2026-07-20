# Cortex

Persistent, tiered memory for AI coding agents. Author notes in an Obsidian-style
vault; Cortex distills them into agent-consumable files and serves them to your
agent at runtime via an MCP server — so your agent shows up to every conversation
already knowing your preferences, patterns, and projects.

```
Build   (vault → agent):   notes  → distill.py    → core-context.md + memory.json
Capture (agent → vault):   agent  → memory_write  → note written → distill.py (auto)
```

## Get Running in One Command

Requires **Python 3.10+**.

```bash
git clone https://github.com/JaySmith/Cortex-AI.git cortex-ai
cd cortex-ai
cortex bootstrap          # create venv + install deps
cortex install            # set up config, distiller, skill
```

`cortex install` is interactive: it prompts for your **vault path** (press Enter
to accept the default — the bundled example vault). It generates
`<vault>/_sync/cortex.yaml`, runs a first distill, and installs the `cortex-ai`
skill. You'll have working distilled output in `<vault>/_sync/distilled/`
immediately.

To skip the prompts (scripting/CI), pass the vault as an argument:

```bash
cortex install /path/to/your/vault
```

## Wire It Into Your Agent

`setup.sh` prints ready-to-paste snippets for both agents at the end. In short:

**opencode** (`opencode.jsonc`):
```jsonc
"mcp": {
  "cortex": {
    "type": "local",
    "command": ["node", "<repo>/mcp/cortex/build/index.js"],
    "enabled": true,
    "environment": {
      "MEMORY_JSON": "<vault>/_sync/distilled/memory.json",
      "VAULT_ROOT": "<vault>",
      "DISTILL_SCRIPT": "<repo>/distill.py",
      "DISTILL_PYTHON": "<repo>/.venv/bin/python"
    }
  }
}
```
Also add `<vault>/_sync/distilled/opencode/core-context.md` to opencode's
`"instructions"` array (the distiller can auto-wire this — see
[docs/QUICKSTART.md](docs/QUICKSTART.md)).

**Claude Desktop** (`claude_desktop_config.json`): same env vars under
`mcpServers.cortex` — full snippet is printed by `setup.sh`.

## How Notes Are Routed

Each note's `tier` frontmatter decides where it goes:

| Tier | Behavior | Use for |
|------|----------|---------|
| `core` | Eager — concatenated into `core-context.md`, always loaded | Preferences, personas, standing rules |
| `skill:<name>` | Lazy — embedded in `skills/<name>/reference.md` | Heavy knowledge loaded only when that skill runs |
| `project` | Lazy — one file per project | Project goals, status, roadmap |
| `vault-only` | Never distilled | Session notes, drafts, logs |

Minimal frontmatter:
```yaml
---
id: my-note
type: knowledge   # knowledge | entity | feedback | decision | session | log
tier: core        # core | skill:<name> | project | vault-only
aliases: ["Human Readable Title"]
---
```
Full spec: [docs/VAULT_SCHEMA.md](docs/VAULT_SCHEMA.md).

## MCP Tools

The server in `mcp/cortex/` exposes these to your agent:

| Tool | Kind | Does |
|------|------|------|
| `memory_search` | read | Keyword search across distilled notes |
| `memory_get` | read | Fetch one note by id |
| `memory_related` | read | Notes related by shared tags + category |
| `memory_write` | write | Create/update a note, then auto-distill |
| `memory_reload` | admin | Force-reload the index |

## Everyday Use

Your config lives at `<vault>/_sync/cortex.yaml`. If it isn't next to `distill.py`,
pass `--config <vault>/_sync/cortex.yaml` to the commands below.

```bash
.venv/bin/python distill.py              # re-distill after editing notes
.venv/bin/python distill.py --dry-run    # preview without writing
.venv/bin/python distill.py --list       # list all notes and their tiers
.venv/bin/python distill.py --show-config # print resolved paths (JSON)
```

## Import an Existing Agent (Backup + Onboard)

Already have an agent set up? `cortex-import.py` backs up its config and seeds the
vault with what it already knows — so you don't start from a blank vault.

```bash
# Preview (writes nothing) — auto-detects common locations
.venv/bin/python cortex-import.py --dry-run

# Import into the example vault (or pass --vault /path/to/your/vault)
.venv/bin/python cortex-import.py
```

**What it reads** (each into a `type: feedback, tier: core` note tagged `review`):

- `AGENTS.md` / `CLAUDE.md`
- opencode `instructions[]` files from `opencode.jsonc`
- `~/.claude/memory/*.md`

**Backup:** before reading anything, every source file — including `opencode.jsonc`,
which the distiller later rewrites — is copied to
`<vault>/_sync/backups/<timestamp>/`. So nothing is lost.

Everything lands with a `review` tag on purpose: imported content isn't
auto-classified, so skim `<vault>/feedback/`, adjust `type`/`tier` where it makes
sense, then re-distill. Override any auto-detected path with
`--agents-md`, `--claude-md`, `--opencode`, or `--claude-memory`.

## Versioning & upgrading

Cortex tracks **two numbers**:

- **Release version** — SemVer in the repo-root **`VERSION`** file. Surfaces in
  `distill.py --version`, the MCP `serverInfo.version`, `package.json`, and
  `_meta.cortex_version` in every `memory.json`. Bump it to cut a release.
- **Schema version** — an integer in **`SCHEMA_VERSION`** describing the on-disk
  data contract. Stamped into `memory.json._meta.schema_version`. This is what
  upgrade-safety compares — not the SemVer.

On every run `distill.py` reconciles code schema vs vault schema: it migrates
forward (auto-backing up `_sync/` first) and refuses to run if the vault is newer
than the code. Check anytime:

```bash
python3 distill.py --config <vault>/_sync/cortex.yaml --check
```

### Upgrading a live install

After pulling new code, use `cortex install --upgrade` to back up the existing
distiller and skill, deploy updated files, and re-distill the live vault:

```bash
git pull
cortex install --upgrade ~/Cortex       # full upgrade
cortex install --upgrade --no-distill   # skip re-distillation
```

Override locations with `VAULT_ROOT`, `SKILLS_DIR` env vars.

The full increment rules (when to bump MAJOR/MINOR/PATCH and the schema) live in
**[CHANGELOG.md](CHANGELOG.md)**.

### Changed your mind?

`cortex install` records install manifests under
`<vault>/_sync/backups/`. To revert Cortex to your machine's pre-install state
(your notes are kept):

```bash
cortex uninstall --vault <vault> --latest          # preview
cortex uninstall --vault <vault> --latest --apply  # revert
```

## Repo Layout

```
VERSION                 Release version (SemVer) — single source of truth
SCHEMA_VERSION          On-disk data-contract version (integer)
CHANGELOG.md            Release history + versioning/upgrade rules
ROADMAP.md              Planned direction for future releases
distill.py              Build pipeline (vault → agent files) + schema check/migrate
cortex-import.py        Backup + import an existing agent's config into the vault
cortex-uninstall.py     Manifest-driven revert to pre-Cortex state (keeps notes)
gen-portfolio.py        Optional: project portfolio from tier:project notes
setup.sh                One-command bootstrap for a fresh install (interactive)
deploy.sh               Upgrade an existing live install (backup-first, idempotent)
cortex.yaml.example     Config template (setup.sh generates a real one at <vault>/_sync/cortex.yaml)
mcp/cortex/             MCP server (runtime read + capture)
skills/cortex-ai/       opencode skill (setup.sh installs it, filling in real paths)
example-vault/          Starter vault — one note per tier, works out of the box
docs/                   overview, QUICKSTART, DEVELOPMENT, VAULT_SCHEMA, EXTENDING, architecture
```

The `version` command in the skill reports the release version (`VERSION`), the
schema version (`SCHEMA_VERSION`), and the MCP server version
(`mcp/cortex/package.json`) — say "cortex version". The `status` command reports
vault health, schema drift, and sync staleness — say "cortex status". Say
"cortex uninstall" to revert Cortex (notes are kept).

## Docs

- [docs/overview.md](docs/overview.md) — what Cortex is and why
- [docs/QUICKSTART.md](docs/QUICKSTART.md) — manual setup + troubleshooting
- [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) — contributing: dev setup, dev loop, releasing
- [docs/VAULT_SCHEMA.md](docs/VAULT_SCHEMA.md) — frontmatter reference
- [docs/EXTENDING.md](docs/EXTENDING.md) — add custom output targets
- [docs/DISTILLATION_SUMMARY.md](docs/DISTILLATION_SUMMARY.md) — architecture
- [mcp/cortex/README.md](mcp/cortex/README.md) — MCP server details
- [ROADMAP.md](ROADMAP.md) — planned direction for future releases

## Related

- **[Cortex-Hub](https://github.com/JaySmith/Cortex-Hub)** — Multi-agent coordination layer. Registry, shared memory, and messaging for AI agents. Optionally sync vault notes across machines via Cortex-Hub's shared memory store.

## License

MIT.

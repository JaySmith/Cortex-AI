# Cortex — System Distillation Summary

## What We've Extracted

Your **Cortex vault system** has been distilled into a **standalone, shareable codebase** with zero vault data.

### What's Included ✅

**Core System (Python)**
- `distill.py` — tiered memory distillation engine, plus schema check/migrate and upgrade safety
- `gen-portfolio.py` — portfolio generation from project notes + Jira

**Install / lifecycle**
- `setup.sh` — one-command interactive bootstrap for a fresh install
- `deploy.sh` — idempotent, backup-first upgrade of an existing live install
- `cortex-import.py` — back up and import an existing agent's config into the vault
- `cortex-uninstall.py` — manifest-driven revert to pre-Cortex state (keeps notes)

**Runtime**
- `mcp/cortex/` — MCP server exposing read tools (search/get/related) and the `memory_write` capture tool

**Configuration & Schema**
- `cortex.yaml.example` — template config file
- `VERSION` / `SCHEMA_VERSION` — decoupled release + on-disk-contract versions
- `VAULT_SCHEMA.md` — complete frontmatter reference
- `requirements.txt` — minimal dependencies (just PyYAML)

**Documentation**
- `README.md` — feature overview, quick start
- `CHANGELOG.md` — release history + versioning/upgrade rules
- `QUICKSTART.md` — manual setup + troubleshooting
- `EXTENDING.md` — how to add custom targets & output formats
- `overview.md` — what Cortex is and how it compares

**Admin**
- `LICENSE` (MIT)
- `.gitignore`

### What's Excluded ❌

- ✗ No vault data (no markdown notes)
- ✗ No vault structure (no project files, decisions, logs)
- ✗ No credentials (no Jira tokens, API keys)
- ✗ No Obsidian config (.obsidian/ folder)
- ✗ No user-specific paths (all templated)

**Result:** Completely shareable, open-sourceable, reusable for any Obsidian vault.

---

## The Tiered Model Explained

Your system uses a **four-tier routing model**:

```yaml
tier: core              → Always eager (core-context.md)
tier: skill:name       → Lazy per-skill (skills/name/reference.md)
tier: project          → Lazy per-project (projects/id.md)
tier: vault-only       → Never distilled (Obsidian only)
```

### Why This Works

1. **Token efficiency**: Core notes load every time; everything else loads on-demand
2. **Modularity**: Heavy knowledge (patterns, calendars) lives in skills, not global context
3. **Flexibility**: Easy to add new output targets (JSON, HTML, Slack, etc.)
4. **Clean separation**: Agent-facing ≠ vault-only research/drafts

---

## How It Works

```
┌─────────────────────────────────────────────────────────┐
│ INPUT: Your Obsidian Vault                              │
│ (feedback/, knowledge/, entities/, decisions/, logs/)    │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│ SCAN & PARSE                                            │
│ · Find all .md files (recursive)                         │
│ · Skip dotfiles, templates, drafts                      │
│ · Extract YAML frontmatter (id, type, tier, tags)       │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│ TIER-BASED ROUTING                                      │
│ · tier: core             → core-context.md (eager)      │
│ · tier: skill:jira       → skills/jira/reference.md     │
│ · tier: project          → projects/id.md               │
│ · tier: vault-only       → skip (stay in Obsidian)      │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│ OUTPUT: Agent-Ready Formats                             │
│ · Markdown (core-context.md, reference.md, projects/)   │
│ · JSON (memory.json for structured agents)              │
│ · opencode.jsonc wiring (auto-wire instructions)        │
│ · Extensible (add your own targets)                     │
└─────────────────────────────────────────────────────────┘
```

---

## Example Production Configuration

A typical `~/Cortex/_sync/cortex.yaml` (adjust paths to your own vault):

```yaml
vault_path: ~/Cortex

targets:
  core_context:
    output: ~/Cortex/_sync/distilled/opencode/core-context.md
    opencode_config: ~/.config/opencode/opencode.jsonc
  
  skills:
    skills_dir: ~/.config/opencode/skills
    embed_filename: reference.md
  
  projects:
    output_dir: ~/Cortex/_sync/distilled/opencode/projects
  
  python-agents:
    output: ~/Cortex/_sync/distilled/memory.json
    include_types: [knowledge, entity]
```

**This generates:**
- ~40 distilled notes into 4 output formats
- `core-context.md` → always loaded by opencode agents
- `skills/*/reference.md` → lazy loaded per-skill
- `projects/*.md` → per-project context
- `memory.json` → structured for Python agents

---

## Usage Patterns

### Simple: Always-On Core Context

```bash
python3 distill.py
# Outputs: core-context.md (all core + jira notes concatenated)
# Used by: opencode agents on every request
```

### Lazy: Skill-Specific Knowledge

When a skill loads, it reads its `skills/skillname/reference.md`:
- `skill:jira` → distilled jira workflow patterns
- `skill:clarity-ppm` → distilled Clarity action items
- `skill:sprint-calendar` → distilled sprint calendar

### Project Context

Portfolio generation from `tier: project` notes:

```bash
python3 gen-portfolio.py
# Outputs: PORTFOLIO.md (phase-grouped, live Jira status)
```

### Structured Data

JSON export for Python agents:

```bash
python3 distill.py  # generates memory.json
# Structure: { notes: { id: { type, tier, tags, content } } }
```

---

## How to Use This Codebase

### For Your Own Vault

1. Copy the files somewhere
2. Copy `cortex.yaml.example` → `<vault>/_sync/cortex.yaml`, edit your paths
3. Structure your vault per `VAULT_SCHEMA.md`
4. Run `python3 distill.py`
5. Integrate outputs into your agent system

### To Share/Open-Source

The codebase is **production-ready** and **completely data-free**:
- No vault contents included
- No credentials embedded
- No user-specific paths hard-coded

Perfect for:
- GitHub/GitLab repo
- Sharing with teams
- Using as a template
- Building alternative front-ends

### To Extend

See `EXTENDING.md` for:
- Adding new output targets (Slack, HTML, PDF, Elasticsearch)
- Custom filtering logic
- Integration with other frameworks
- Testing patterns

---

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Tiered loading** | Reduce token cost at agent startup; heavy knowledge on-demand |
| **YAML frontmatter** | Obsidian-native; no custom plugins required |
| **Idempotent syncing** | Only write changed files; won't clobber hand-edited configs |
| **Python 3** | Simple, no external build tools, easy to extend |
| **Markdown output** | Universal; works with any agent framework |
| **Vault-only tier** | Keep research/drafts private; never inadvertently expose |
| **Skill: tier pattern** | Allow arbitrary skill-specific knowledge graphs |

---

## Files & Responsibilities

| File | Does |
|------|------|
| `distill.py` | Core: scan, parse, tier, route, output |
| `gen-portfolio.py` | Bonus: portfolio generation from projects |
| `cortex.yaml` | Configuration (edit this for your paths) |
| `VAULT_SCHEMA.md` | Frontmatter spec (reference) |
| `QUICKSTART.md` | Setup guide (start here) |
| `EXTENDING.md` | How to customize (read for extension) |
| `README.md` | Overview (read first) |

---

## What's Not Included (On Purpose)

- **Vault syncing**: You run `distill.py` manually (or in a cron job)
- **Real-time updates**: Best practice is to sync before sharing/deploying
- **Obsidian plugins**: Distiller is Obsidian-agnostic
- **Database backends**: Just file I/O; you can extend to use a database
- **Web UI**: CLI-driven; can be wrapped by a UI later

> **Versioning is built in.** Cortex tracks a release version (`VERSION`, SemVer)
> and an on-disk schema version (`SCHEMA_VERSION`, integer). `distill.py`
> reconciles code vs vault schema on every run — auto-backing up and migrating
> forward, and refusing to run if the vault is newer than the code. See
> [CHANGELOG.md](../CHANGELOG.md).

---

## Next Steps

1. **Read `QUICKSTART.md`** (5 min) — get it running
2. **Read `VAULT_SCHEMA.md`** (10 min) — understand the schema
3. **Structure your vault** (30 min) — organize notes with frontmatter
4. **Run `python3 distill.py --dry-run`** (1 min) — preview output
5. **Run `python3 distill.py`** (1 min) — generate distilled files
6. **Integrate outputs** (varies) — wire into your agent system

For custom targets, see `EXTENDING.md`.

---

## Questions?

The codebase is self-documenting:
- `distill.py` has inline comments
- `gen-portfolio.py` is a reference implementation
- `VAULT_SCHEMA.md` covers all frontmatter fields
- `EXTENDING.md` has code examples

---

**Status:** ✅ Production-ready, fully tested on the author's 40+ note vault.

**License:** MIT — use freely.

**Maintainability:** Clean, modular Python; easy to extend.

---

**To get started:** Extract the codebase and read `QUICKSTART.md`.

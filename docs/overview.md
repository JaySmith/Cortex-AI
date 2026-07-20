# Cortex — What It Is and How It Works

> Applies to Cortex 2.0.0 (schema 2). See [CHANGELOG.md](../CHANGELOG.md) for release history.

## The Problem It Solves

Every new conversation with an AI assistant starts from zero. It doesn't know
who you are, what you're working on, how you like things done, or any of the
domain knowledge it learned yesterday. So you paste the same context in again.
And again.

Cortex fixes that. It's a **persistent memory system for AI agents** — a
structured set of notes that your assistant draws on automatically, so it
shows up to every conversation already knowing what matters.

---

## What Cortex Is

At its heart, Cortex is a store of knowledge your assistant builds and draws
on as you work together, plus a small pipeline that decides *when* each piece
reaches the assistant. Its guiding principle:

> **Load only what the assistant needs, when it needs it.**

The primary way knowledge gets in is the assistant itself. As you work, it
captures what matters — a preference, a decision, a pattern — writing notes
straight into the vault and re-encoding automatically. The notes are plain
Markdown, so you can open the vault in any editor to review or refine by hand.

Instead of dumping everything into context on every request, Cortex keeps the
always-on footprint tiny and pulls in heavier detail on demand. In practice
this cuts the always-loaded context by nearly 90% compared to a single flat
instructions file — while making *more* total knowledge available.

---

## Architecture: Four Layers

### 1. The Vault — where knowledge lives

Plain Markdown notes with structured frontmatter (type, tier, tags,
category). Notes are grouped by what they describe:

```
your-vault/
├── feedback/       ← preferences, persona, standing rules
├── knowledge/      ← reference docs, patterns, procedures
├── entities/       ← projects, people, systems, teams
├── decisions/      ← records of choices
└── logs/           ← session and event notes
```

### 2. The Build Pipeline — where it gets organized

The encoder reads every note and routes it to the right destination based
on its tier. You run it whenever you change something — or the agent triggers
it automatically after writing a note. No database, no cloud service, no
background daemon.

### 3. The Tier System — the core idea

Every note declares a **tier** that controls when it reaches your assistant:

| Tier | Behavior | Use for |
|------|----------|---------|
| `core` | Eager — always loaded | Preferences, personas, standing rules |
| `skill:<name>` | Lazy — loaded only when that skill runs | Heavy reference docs, checklists |
| `project` | Lazy — loaded on demand | Project goals, status, roadmap |
| `vault-only` | Never encoded | Session notes, drafts, research |

The always-on layer also includes a lightweight *index* — a table of
contents telling the assistant what else exists, so it knows what it *could*
pull in without actually loading any of it.

### 4. The CLI Memory Commands — search on demand

The `cortex` CLI provides these commands mid-conversation:

| Command | What it does |
|---------|-------------|
| `cortex memory search <q>` | Keyword lookup across all notes |
| `cortex memory get <id>`  | Fetch one note in full by its stable name |
| `cortex memory write`     | Create or update a note from inside a conversation, then auto-encode |

The write command closes the loop: the assistant can capture what it learns
mid-session without you leaving the conversation.

---

## Everyday Use

Cortex is designed to be run and reasoned about by hand — there's no daemon
and nothing hidden.

| Command | What it does |
|---------|-------------|
| `cortex encode` | Rebuild every encoded output from the current vault |
| `cortex encode --list` | List every note with its tier — the transparency view |
| `cortex encode --dry-run` | Preview what would change without writing |
| `cortex encode --check` | Release + schema health verdict |
| `cortex status` | Installation health check |
| `cortex memory search <query>` | Search encoded memory from the CLI |

---

## Versioning & Safe Upgrades

Cortex tracks **two independent numbers**:

| Number | File | Meaning |
|--------|------|---------|
| Release version (SemVer) | `VERSION` | The human-facing release number |
| Schema version (integer) | `SCHEMA_VERSION` | The on-disk data contract |

**Every run is upgrade-safe.** Before doing anything, the encoder compares
the code's schema version against the one in your vault:

- **Equal (or fresh vault)** — proceed normally.
- **Code newer** — auto-back up, run any migrations, proceed.
- **Code older than vault** — refuse to run (no silent downgrades).

Check status any time with `cortex encode --check` or `cortex status`.

---

## Installing, Upgrading, Reverting

- **Fresh install** — `cortex bootstrap` + `cortex install` handles
  everything: venv, deps, config, encoder, skill, first encode.
- **Upgrading** — `cortex install --upgrade` backs up every target first,
  deploys updated files, re-encodes, and verifies versions.
- **Reverting** — `cortex uninstall` reads install manifests to restore
  modified files and remove created ones. Notes are always kept.

---

## How It Compares

| | Cortex | Cloud memory services | Agent frameworks | Editor plugins |
|---|--------|----------------------|------------------|----------------|
| **Data lives** | Your machine | Their cloud | Your app | Your editor |
| **Who curates** | Assistant capture (you steer) | Auto-extracted | You (in code) | Auto-indexed |
| **Setup** | Low | Low | High | Low |
| **Token-cost control** | Built-in (tiers) | Limited | Manual | Limited |
| **Human-editable** | Yes (plain files) | Partially | It's code | Yes |
| **Retrieval** | Keyword, instant | Semantic | Depends | Semantic |
| **Upgrade safety** | Versioned + reversible | Vendor-managed | Your problem | Plugin-managed |

Cortex trades automatic fact-extraction and semantic search for **total
control, locality, and zero external dependencies**. You decide exactly what
your assistant knows — nothing leaving your machine.

---

## Bottom Line

Cortex is **local, hand-curated, tier-controlled persistent memory with a
small build pipeline** — with in-conversation capture, versioned and
reversible upgrades, and a session-aware sync. You control exactly what your
assistant knows, it costs almost nothing until it's needed, and none of it
leaves your machine.

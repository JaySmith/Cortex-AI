# Cortex — What It Is and How It Works

> Applies to Cortex 1.2.1 (schema 1). See [CHANGELOG.md](../CHANGELOG.md) for release history.

## The Problem It Solves

Every new conversation with an AI assistant starts from zero. It doesn't know
who you are, what you're working on, how you like things done, or any of the
domain knowledge it learned yesterday. So you paste the same context in again.
And again. It's slow, it burns tokens, and the assistant is only ever as good as
what you remembered to include this time.

Cortex fixes that. It's a **persistent memory system for AI agents** — a
structured set of notes that your assistant can draw on automatically, so it
shows up to every conversation already knowing what matters.

---

## What Cortex Is

At its heart, Cortex is a store of knowledge your assistant builds and draws on
as you work together, plus a small pipeline that decides *when* each piece
reaches the assistant. Its guiding principle is simple:

> **Load only what the assistant needs, when it needs it.**

The primary way knowledge gets in is the assistant itself. As you work, it
captures what matters — a preference you state, a decision you make, a pattern
it just worked out — writing each straight into the vault mid-conversation and
re-distilling automatically. Nothing to switch to, nothing to remember to save.
The notes are plain Markdown, so you're free to open the vault in any editor to
review, refine, or add to them by hand — but that's an option, not a
requirement. The everyday loop is: talk to your assistant, and it keeps its own
memory current.

Instead of dumping everything into context on every request, Cortex keeps the
always-on footprint tiny and pulls in heavier detail on demand. In practice this
cut the always-loaded context by nearly 90% compared to a single flat
instructions file — while making *more* total knowledge available.

---

## Architecture: Four Layers

### 1. The Vault — where knowledge lives

Plain Markdown notes with a little structured header (type, tier, tags,
category). Your assistant writes them as you work; you can open the vault in any
Markdown editor whenever you want to review or refine by hand. Notes are grouped
by what they describe:

```
Cortex/
├── entities/     ← projects, people, systems, teams
├── knowledge/    ← reference docs, patterns, procedures
├── feedback/     ← your preferences and working style
├── decisions/    ← records of choices you've made
└── logs/         ← session and event notes (kept private)
```

### 2. The Build Pipeline — where it gets organized

A small set of scripts reads every note and routes it to the right destination
based on its tier (see below). You run it whenever you change something. No
database, no cloud service, no background daemon — just files in, files out.

### 3. The Tier System — the core idea

Every note declares a **tier** that controls when it reaches your assistant.
This is what keeps token cost low without sacrificing knowledge:

| Tier | Reaches the assistant… |
|------|------------------------|
| **Always-on** | Every single conversation — your identity, preferences, core rules |
| **Skill-scoped** | Only when a related capability is active — heavy reference docs load lazily |
| **Project** | On demand, when a specific project comes up |
| **Private** | Never leaves the vault — drafts, research, sensitive notes |

The always-on layer also includes a lightweight *index* — a table of contents
telling the assistant what else exists, so it knows what it *could* pull in
without actually loading any of it.

### 4. The Runtime Query Layer — search on demand

A small service exposes your notes to the assistant as searchable tools mid-
conversation:

| Tool | What it does |
|------|-------------|
| **Search** | Keyword lookup across all notes |
| **Get** | Fetch one note in full by its stable name |
| **Related** | Find notes connected to a given one by shared tags and category |
| **Write** | Create or update a note from inside a conversation, then re-distill automatically |

This is the "retrieve" step of a retrieval-augmented setup — but lightweight,
local, and instant, with no vector database to run. The write tool closes the
loop: the assistant can capture what it learns mid-session without you leaving
the conversation.

---

## Feature Summary

| Feature | What it gives you |
|---------|-------------------|
| **Persistent identity** | The assistant remembers who you are and how you work, every time |
| **On-demand project context** | Deep project detail loads only when that project comes up |
| **Skill-scoped reference** | Bulky API docs, checklists, and procedures load only when relevant |
| **Live search & write** | The assistant can pull any note into a conversation — or capture a new one — as needed |
| **Guided note authoring** | A simple flow to add new notes from templates |
| **Session capture** | A "sync" reconciles what was learned this session into the vault before rebuilding |
| **Portfolio / dashboard views** | Generate a rolled-up summary across all your projects |
| **Full transparency** | List everything in the vault and see exactly which tier it sits in |
| **Safe upgrades** | Schema-versioned data with automatic backups and migrations on every run |
| **Clean revert** | Uninstall returns the machine to its pre-Cortex state while keeping your notes |

---

## Operating Cortex

Cortex is designed to be run and reasoned about by hand — there's no daemon and
nothing hidden. Day-to-day it comes down to a handful of moves.

### Everyday commands

| Command | What it does |
|---------|-------------|
| `distill.py` | Rebuild every distilled output from the current vault |
| `distill.py --list` | List every note with its tier — the transparency view |
| `distill.py --dry-run` | Preview what would change without writing |
| `distill.py --show-config` | Print resolved paths and version/schema numbers as JSON |
| `distill.py --check` | Plain-language release + schema health verdict |
| `gen-portfolio.py` | Generate a phase-grouped project dashboard with live status |

If your config isn't next to `distill.py`, add
`--config <vault>/_sync/cortex.yaml` to each call. The assistant also exposes
these as spoken commands through its Cortex skill: `search`, `get`, `related`,
`list`, `add`, `capture`, `sync`, `status`, `version`, `open`, `portfolio`,
`import`, and `uninstall`.

### Sync is capture-then-rebuild

A "sync" is **not** just a rebuild. It's the moment to reconcile everything worth
remembering from the current session *into* the vault before regenerating the
distilled outputs — otherwise the rebuild just re-emits stale knowledge and the
session's lessons are lost. So a sync always runs in two steps:

1. **Capture** — scan the session for new preferences, decisions, patterns, and
   lessons, and write each into the vault (updating an existing note where one
   fits, rather than duplicating).
2. **Rebuild** — run the distiller to regenerate the always-on context, the
   skill references, and the project files.

Individual writes already trigger a rebuild in the background, so the explicit
rebuild step mainly matters after a batch of manual edits.

---

## Versioning & Safe Upgrades

Cortex tracks **two independent numbers**, on purpose:

| Number | File | Meaning |
|--------|------|---------|
| **Release version** (SemVer, e.g. `1.2.0`) | `VERSION` | Which release of the toolchain this is — the human-facing number |
| **Schema version** (integer, e.g. `1`) | `SCHEMA_VERSION` | The on-disk data contract: the shape of the exported index, required frontmatter, and config keys |

Decoupling them means a routine release can never silently break your data, and a
big feature release doesn't have to disturb the data contract. The release number
follows ordinary SemVer rules (breaking / feature / fix); the schema number only
moves when the on-disk format actually changes.

**Every run is upgrade-safe.** Before doing anything, the distiller compares the
code's schema version against the one stamped in your vault:

- **Equal (or a fresh vault)** → proceed normally.
- **Code newer** → automatically back up the working directory, run any registered
  migrations, then proceed.
- **Code older than the vault** → refuse to run, rather than risk misreading newer
  data. No silent downgrades.

Migrations are idempotent and only ever touch Cortex's own working files — never
your notes. Check status any time with `distill.py --check`.

---

## Installing, Upgrading, Reverting

- **Fresh install** — `setup.sh` bootstraps everything interactively: deps, MCP
  server build, generated config, first distill, and the installed skill.
- **Upgrading a live install** — `deploy.sh` upgrades an existing install whose
  pieces live in separate locations (distiller under `<vault>/_sync/`, MCP under
  the agent's MCP home, skill under the skills dir). It's idempotent, backs up
  every target first, re-distills, verifies the schema, and refuses to downgrade a
  newer vault. Dry-run by default.
- **Reverting** — both `setup.sh` and `cortex-import.py` record **manifests** of
  every file they create, modify, or back up. `cortex-uninstall.py` reads those
  manifests to restore modified files and remove created ones, returning the
  machine to its pre-Cortex state. It previews by default and only changes things
  on `--apply` — and **your vault notes are always kept**.

---

## How It Compares

### At a glance

| | Cortex | Cloud memory services | Agent frameworks | Editor plugins |
|---|--------|----------------------|------------------|----------------|
| **Where data lives** | Your machine | Their cloud | Your app | Your editor |
| **Who curates it** | Assistant capture (you steer) | Auto-extracted | You (in code) | Auto-indexed |
| **Setup complexity** | Low | Low | High | Low |
| **Token-cost control** | Built-in (tiers) | Limited | Manual | Limited |
| **Human-editable** | Yes (plain files) | Partially | It's code | Yes |
| **Retrieval** | Keyword, instant | Semantic | Depends | Semantic |
| **Upgrade safety** | Versioned + reversible | Vendor-managed | Your problem | Plugin-managed |
| **Best for** | One person's long-term context | Products that learn from users | Building agent apps | Searching a knowledge base |

The short version: Cortex trades automatic fact-extraction and semantic search
for **total control, locality, and zero external dependencies**. You decide
exactly what your assistant knows — no surprises, nothing leaving your machine.

### Under the hood

For readers who want the technical detail:

**vs. runtime-tiered memory systems (e.g. MemGPT / Letta).** These implement
memory tiers *inside* the agent runtime — core memory always in context,
archival memory behind a vector search, recall memory for recent turns, with
automatic summarization moving data between them. Cortex mirrors the same tier
concept but **externalizes it to the file system**. There's no automatic
promotion or summarization between tiers — the assistant captures and classifies
notes as you work, and you can adjust any of them by hand — which makes it
dramatically simpler to run and inspect, at the cost of the runtime automation.

**vs. managed memory services (e.g. Mem0).** These sit in the cloud and
automatically extract facts from your conversations, storing them in their cloud
for later recall. Cortex captures in-conversation too, but keeps everything local
and under your review: the assistant proposes what to remember, and you can see,
edit, or remove any of it. You get capture *and* control with guaranteed privacy;
what you give up is opaque, hands-off cloud extraction.

**vs. code-first memory modules (e.g. LangChain / LlamaIndex).** These are
libraries for wiring memory into an application you're building. They're
powerful for shipping products but aren't designed to be one person's durable,
hand-tended context across every tool they use. Cortex is closer to a personal
knowledge base with an assistant interface attached.

**vs. editor-based semantic search (e.g. note-app AI plugins).** These keep
everything in the editor and retrieve by embedding similarity. Cortex uses the
editor purely for authoring and exports to a build pipeline instead. Its
retrieval is keyword-scored rather than semantic — less nuanced, but zero
latency and no embedding model or vector store to maintain.

**On the scoring model.** Search ranks notes by weighted matches across the
note's name, aliases, tags, category, and body — name and alias hits score
highest, body matches lowest. "Related" scoring weights shared tags most
heavily, then category, then type. It's deliberately simple and explainable —
you can predict what will come back — which suits a system where a human curates
the corpus.

---

## Bottom Line

Cortex is **local, hand-curated, tier-controlled persistent memory with a small
build pipeline** — now with in-conversation capture, versioned and reversible
upgrades, and a session-aware sync. It's less automated than cloud memory
services, more structured than a single flat instructions file, and more
human-friendly than a code-first framework. That tradeoff is the whole point: you
control exactly what your assistant knows, it costs almost nothing until it's
needed, and none of it leaves your machine.

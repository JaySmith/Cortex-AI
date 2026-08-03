# Roadmap

Direction for future Cortex releases. This is a planning document, not a
commitment — items move, merge, and drop as priorities shift. Shipped work is
recorded in [`CHANGELOG.md`](./CHANGELOG.md); this file is only for what's ahead.

Current release: **2.0.0** (see `cortex/__init__.py`).

---

## Shipped — Cortex Hive (remote vault federation)

Multiple agents on multiple machines share a centralized vault of long-term
knowledge via cortex-hub. cortex-ai is the brain; cortex-hub is the nervous
system. The agent talks to the Python CLI over subprocess (unchanged). The CLI
optionally federates to a shared hub over HTTP.

**Full design and implementation plan:**
[`docs/hive-integration.md`](docs/hive-integration.md)

**Summary:** Python hub client in `cortex/encoder/core.py`, new `hive:` config block,
`--hive-push` / `--hive-pull` / `--hive-status` CLI commands, `hive`
frontmatter field on notes. Newest `updated` timestamp wins for conflict
resolution (v1). Bearer token auth and section-aware merge deferred to later
phases.

**Release impact:** MINOR (1.3.0). Schema bump v1→v2.

**Status:** Phases 1–7 implemented and committed.
- Phase 1: Config + schema migration ✅
- Phase 2: Python hub client (`cortex/hub/client.py`) ✅
- Phase 3: CLI commands (`--hive-push/pull/status`) ✅
- Phase 4: Hive frontmatter (`VaultNote.hive`) ✅
- Phase 5: MCP server hive proxy — removed in v2.0.0 (MCP server removed) 🗑️
- Phase 6: Skill commands (`cortex hive status/push/pull/setup`) ✅
- Phase 7: Bearer token auth (cortex-hub side) ✅

---

## Shipped — vault lint (`cortex lint`)

A CLI lint command that scans the vault for common issues. 11 rules across three
severity levels, auto-fix for the most common ones, `--strict` mode, `--json`
output, `--note <id>` single-note scanning.

| Severity | Rules | Auto-fix |
|----------|-------|:--------:|
| E | missing-id, missing-type, missing-tier, invalid-tier, duplicate-id | type & tier ✓ |
| W | missing-aliases, slug-mismatch, dangling-wiki-link, non-slug-id | aliases ✓ |
| I | missing-updated, empty-body | |

**Implementation:** `cortex/cli/lint.py`, `cortex/vault/links.py` (shared link
resolution with encoder), registered in `cortex/cli/main.py`. 21 tests.

**Shipped in:** v2.0.0

---

## Shipped — vault relationship graph (`cortex encode --graph`)

`cortex encode --graph` parses `[[wiki-link]]` references across all note bodies
and exports a directed graph to `encoded/graph.json`:

- **Nodes** — every note with its type, category, and degree
- **Edges** — resolved link pairs (source → target via id or alias)
- **Dangling** — links to note ids that don't exist
- **Isolated** — nodes with zero inbound or outbound links
- **God nodes** — high-degree notes (central to the vault; > median + 2σ)

**Implementation:** `build_wiki_graph()` in `cortex/encoder/core.py`, shared
link resolution in `cortex/vault/links.py`.

**Shipped in:** v1.4.0

---

## Shipped — CLI memory commands

The MCP server was removed in v2.0.0. All memory operations are now CLI commands:

| Command | What it does |
|---------|-------------|
| `cortex memory get <id>` | Fetch a single note by id (memory.json, fallback to file) |
| `cortex memory list` | Table of all notes with `--tier`/`--type` filters |
| `cortex memory write` | Create or update a note, auto-triggers encode |
| `cortex memory search <query>` | Keyword search across memory.json |

**Shipped in:** v2.0.0 (breaking)

---

## Shipped — cross-platform parity (Windows / Linux / macOS)

Cortex runs on all three platforms.

- Multi-agent platform support (OpenCode/Codex/Copilot installers)
- `cortex init` templates
- `cortex upgrade`
- Enhanced `cortex doctor` with structured error messages
- Cross-platform venv resolution in `_resolve_encode_python()` and `cortex bootstrap`
- ruff/mypy/pre-commit/CI

**Remaining:**
- Verify the fire-encode subprocess path works on Windows end-to-end after `uv tool install`.

---

## Future — enhanced retrieval (only if keyword proves insufficient)

The keyword scorer handles canonical queries well. Cortex's curated vocabulary
(human-chosen ids, aliases, and tags that agents are trained to use) partially
mitigates vocabulary-mismatch retrieval failures by design.

If synonym or conceptual-proximity failures are observed in practice — searching
for something, getting no results, and knowing the note exists — a vector sidecar
(`encoded/embeddings.json`) could be added: embeddings generated at encode
time, stored outside the vault, invisible to Obsidian. Human readability of all
vault `.md` files is fully preserved. The CLI `memory search` would use
keyword-first, vector-fallback. No speed gain — this is an accuracy improvement
for vocabulary mismatch only, and only worthwhile if the failure mode is observed
repeatedly in practice.

**Trigger:** do not implement without concrete evidence of a retrieval gap.
`memory.json` remains RAG-ready if this day comes.

---

## Future — multi-platform agent routing (`agents:` field)

The `agents:` frontmatter field is already parsed by `cortex/encoder/core.py` (as
`VaultNote.agents`) but not yet used for routing. Today Cortex serves one agent
platform (opencode). When multiple platforms are in use (opencode, claude-code,
copilot-studio), the encoder could filter each platform's output to only
include notes tagged for it.

**Benefit:** a single vault serves heterogeneous agents without each one
receiving knowledge irrelevant to it — opencode-specific skill notes stay out of
a claude-code context, and vice versa. The hook already exists in the codebase;
this is a routing wiring job, not a data model change.

No design committed; implement when a second agent platform actively consumes the
vault.

---

## Future — temporal fact lifecycle (`expires_at`)

A note could carry `expires_at: "YYYY-MM-DD"` frontmatter. `cortex encode` would
skip expired notes at encoding time; `memory search` would filter them at
retrieval time. Useful for temporary context: sprint-specific notes, meeting
prep, short-lived project state that should not persist indefinitely.

**Benefit:** temporary facts age out automatically instead of accumulating as
stale context. The agent capture protocol could reason about whether a fact is
temporary and set this field at write time.

No implementation until the need arises — manual curation via the `vault-only`
tier and note deletion is sufficient for now.

---

## Future — skill optimizer

A `cortex skill optimize` command that audits installed skills for efficiency
and auto-load correctness.

**Auto-load audit:**
- Each skill's `description` field is checked against the skill's actual triggers
  and content — missing or overly narrow trigger phrases are flagged.
- Skills with overlapping descriptions are detected so loading conflicts can be
  resolved (only one skill loads per match).

**Token budget:**
- Enforces the SKILL.md ≤ 100 lines / ≤ 700 tokens convention.
- Flags oversized inline reference tables that should be moved to `reference.md`.
- Reports per-skill load-time token cost.

**Implementation:** a new `cortex/skill_optimizer.py` module that reads
`~/.config/opencode/skills/*/SKILL.md`, parses descriptions, measures line/token
counts, and outputs a report. Suggested fixes for each violation. `--fix` flag
rewrites descriptions for broader trigger coverage and splits oversized files.

**Trigger:** implement when skill count exceeds 10+ or load-time token bloat is
observed.

## Contributing to this roadmap

Per the repo-first rule, plan here (or in the vault) before building, and always
modify the gold-standard repo before redeploying to any live install. When an item
ships, remove it from this file and record it in `CHANGELOG.md`.

# Roadmap

Direction for future Cortex releases. This is a planning document, not a
commitment — items move, merge, and drop as priorities shift. Shipped work is
recorded in [`CHANGELOG.md`](./CHANGELOG.md); this file is only for what's ahead.

Current release: **1.2.2** (see `VERSION`).

---

## Shipped — Cortex Hive (remote vault federation)

Multiple agents on multiple machines share a centralized vault of long-term
knowledge via cortex-hub. cortex-ai is the brain; cortex-hub is the nervous
system. The agent talks to a local MCP server over stdio (unchanged). The local
server optionally federates to a shared hub over HTTP.

**Full design and implementation plan:**
[`docs/HIVE-INTEGRATION.md`](docs/HIVE-INTEGRATION.md)

**Summary:** Python hub client in `distill.py`, new `hive:` config block,
`--hive-push` / `--hive-pull` / `--hive-status` CLI commands, `hive`
frontmatter field on notes, optional MCP server proxy for real-time sync.
Newest `updated` timestamp wins for conflict resolution (v1). Bearer token
auth and section-aware merge deferred to later phases.

**Release impact:** MINOR (1.3.0). Schema bump v1→v2. No new hub tools —
uses existing `hub_memory_*` API. No changes to cortex-hub.

**Status:** Phases 1–6 implemented and committed. Phase 7 (bearer auth) deferred.
- Phase 1: Config + schema migration ✅
- Phase 2: Python hub client (`hive_client.py`) ✅
- Phase 3: CLI commands (`--hive-push/pull/status`) ✅
- Phase 4: Hive frontmatter (`VaultNote.hive`) ✅
- Phase 5: MCP server hive proxy (`hub-client.ts`) ✅
- Phase 6: Skill commands (`cortex hive status/push/pull/setup`) ✅
- Phase 7: Bearer token auth (cortex-hub side) ⏳

---

## Ongoing — cross-platform parity (Windows / Linux / macOS)

Cortex should run identically on all three platforms.

- **Done (1.2.2):** `distill.py` / `gen-portfolio.py` self-bootstrap into `.venv`
  with a Windows-aware interpreter path (`Scripts/python.exe` vs `bin/python`).
- **Remaining:**
  - `deploy.sh` and `setup.sh` are bash-only — need a Windows install/deploy path
    (PowerShell scripts or a cross-platform Python entrypoint).
  - Audit any remaining POSIX assumptions in shell tooling.
  - Verify the MCP server's `fireDistill` venv resolution on Windows end-to-end.

---

## Someday — enhanced retrieval (only if keyword proves insufficient)

The keyword scorer handles canonical queries well. Cortex's curated vocabulary
(human-chosen ids, aliases, and tags that agents are trained to use) partially
mitigates vocabulary-mismatch retrieval failures by design.

If synonym or conceptual-proximity failures are observed in practice — searching
for something, getting no results, and knowing the note exists — a vector sidecar
(`distilled/embeddings.json`) could be added: embeddings generated at distill
time, stored outside the vault, invisible to Obsidian. Human readability of all
vault `.md` files is fully preserved. The MCP `memory_search` would use
keyword-first, vector-fallback. No speed gain — this is an accuracy improvement
for vocabulary mismatch only, and only worthwhile if the failure mode is observed
repeatedly in practice.

**Trigger:** do not implement without concrete evidence of a retrieval gap.
`memory.json` remains RAG-ready if this day comes.

---

## Someday — multi-platform agent routing (`agents:` field)

The `agents:` frontmatter field is already parsed by `distill.py` (as
`VaultNote.agents`) but not yet used for routing. Today Cortex serves one agent
platform (opencode). When multiple platforms are in use (opencode, claude-code,
copilot-studio), the distiller could filter each platform's output to only
include notes tagged for it.

**Benefit:** a single vault serves heterogeneous agents without each one
receiving knowledge irrelevant to it — opencode-specific skill notes stay out of
a claude-code context, and vice versa. The hook already exists in the codebase;
this is a routing wiring job, not a data model change.

No design committed; implement when a second agent platform actively consumes the
vault.

---

## Someday — temporal fact lifecycle (`expires_at`)

A note could carry `expires_at: "YYYY-MM-DD"` frontmatter. `distill.py` would
skip expired notes at distillation time; `memory_search` would filter them at
retrieval time. Useful for temporary context: sprint-specific notes, meeting
prep, short-lived project state that should not persist indefinitely.

**Benefit:** temporary facts age out automatically instead of accumulating as
stale context. The agent capture protocol could reason about whether a fact is
temporary and set this field at write time.

No implementation until the need arises — manual curation via the `vault-only`
tier and note deletion is sufficient for now.

---

## Someday — vault relationship graph (`distill.py --graph`)

Obsidian `[[wiki-link]]` references in note bodies are invisible to the distiller
today — they're just text. A `--graph` command could parse them into a directed
graph (source note → linked note) and export insight artifacts:

- `distilled/graph.json` — queryable edge list
- `distilled/graph.html` — interactive visualization (pan / zoom / search)
- **Dangling links** — a note links to an id that doesn't exist yet
- **Isolated nodes** — notes with zero inbound or outbound links
- **God nodes** — high-degree notes central to the vault

**Benefit:** structural insight for maintaining and navigating the vault. See
which notes are foundational (high-degree → candidates for tier promotion), spot
orphaned notes that should link somewhere, and catch dangling references. Inspired
by Graphify's "god nodes" and graph export, but scoped to wiki-link parsing over
Markdown — no Tree-sitter, no LLM extraction, no community-detection stack
(overkill for a few dozen curated notes). A ~150-line Python addition using
NetworkX, fitting cleanly into the existing `distill.py` ecosystem.

No implementation until vault navigation becomes a felt need; `cortex list` and
`memory_related` cover most cases at current scale.

---

## Contributing to this roadmap

Per the repo-first rule, plan here (or in the vault) before building, and always
modify the gold-standard repo before redeploying to any live install. When an item
ships, remove it from this file and record it in `CHANGELOG.md`.

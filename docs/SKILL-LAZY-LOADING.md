# Design Doc: Cortex Skill Lazy Loading

## Problem

Agent context windows are finite. Cortex maintains a vault of potentially hundreds
of notes, but most sessions only need a fraction of that knowledge. Loading
everything eagerly wastes tokens and degrades reasoning quality.

## Solution: Two-Layer Lazy Loading

Cortex implements lazy loading at two distinct layers that compose together:

### Layer 1: opencode Skill Tool (framework layer)

opencode discovers all `SKILL.md` files at boot but only injects **lightweight
summaries** (name + description) into the system prompt's `<available_skills>`
block. The full SKILL.md content (~435 lines for cortex-ai) enters the
conversation **only when the agent calls `skill(name="cortex-ai")`**.

```
Boot time:  <available_skills> block (~20 tokens per skill)
            ├── cortex-ai: "Work with the Cortex vault — search notes..."
            ├── homelab: "Expert in homelab infrastructure..."
            └── sms: "SMS via email gateway..."

Runtime:    skill(name="cortex-ai") → full 435-line SKILL.md injected
            (only when the user triggers a cortex operation)
```

**Token savings:** ~3,000 tokens per session if cortex isn't used.

### Layer 2: Cortex Tier System (distiller layer)

Within the vault, notes declare a `tier` that controls when/how they reach
the agent:

| Tier | Loading | Output | When loaded |
|------|---------|--------|-------------|
| `core` | **Eager** | `core-context.md` → opencode `instructions[]` | Every session, unconditionally |
| `skill:<name>` | **Lazy** | `skills/<name>/reference.md` | Only when skill is invoked |
| `project` | **Lazy** | `distilled/projects/<id>.md` | Only when project is discussed |
| `vault-only` | **Never** | Nothing (stays in Obsidian) | Never |

**The distiller (`distill.py`) routes notes at build time:**

```
vault notes → distill.py scan → tier routing:
  core ──────────────→ core-context.md (eager, always loaded)
  skill:homelab ─────→ skills/homelab/reference.md (lazy)
  skill:cortex-ai ───→ skills/cortex-ai/reference.md (lazy)
  project ───────────→ projects/<id>.md (lazy)
  vault-only ────────→ skip
```

**The on-demand pointer index** in `core-context.md` (lines 504-529 of
`distill.py`) tells the agent which skills contain what knowledge, without
loading that knowledge:

```markdown
## On-Demand Memory (load only when relevant)

Specialized knowledge lives in skills. Invoke the skill and read its `reference.md`:

- **homelab** skill — Proxmox cluster, VLAN layout, Docker compose
- **cortex-ai** skill — vault-capture-rules, tier conventions

Project context (read the file when the project comes up):
- **Project Alpha** — `/path/to/projects/project-alpha.md`
```

## How the Layers Compose

The full lazy loading flow:

```
1. BOOT
   opencode scans ~/.config/opencode/skills/**/SKILL.md
   → Parses frontmatter → registers {name, description, location}
   → System prompt gets <available_skills> block (summaries only)

2. BOOT (parallel)
   opencode loads instructions[] which includes core-context.md
   → Agent sees eager core notes + on-demand pointer index
   → Agent knows skill:homelab has "Proxmox cluster, VLAN layout"
     (but content NOT loaded)

3. RUNTIME — user says "check my homelab network"
   Agent recognizes homelab skill is relevant
   → Calls skill(name="homelab")
   → Full SKILL.md injected into context (17 lines, lightweight)

4. RUNTIME — user says "cortex search proxmox"
   Agent recognizes cortex-ai skill is relevant
   → Calls skill(name="cortex-ai")
   → Full SKILL.md injected (435 lines)
   → Agent uses MCP tools (cortex_memory_search, etc.)
   → MCP server searches memory.json, returns results
```

**Key insight:** There are two independent lazy-load boundaries:

1. **Skill SKILL.md** — loaded on `skill()` call (Layer 1)
2. **Vault reference.md** — embedded in the skill directory, loaded when the
   skill SKILL.md instructs the agent to read it (Layer 2)

## Progressive Disclosure Model

The two-layer system forms a **three-stage progressive disclosure** pipeline.
Each stage reveals exactly as much information as the agent needs to decide
whether to go deeper:

```
Stage 1: SUMMARY          Stage 2: INSTRUCTIONS      Stage 3: KNOWLEDGE
(always in context)       (on skill() call)          (on file read)
┌─────────────────┐      ┌─────────────────┐        ┌──────────────────┐
│ <available_     │      │ cortex-ai       │        │ cortex — Reference│
│   skills> block │      │ SKILL.md        │        │ (auto-generated)  │
│                 │      │                 │        │                  │
│ cortex-ai:      │  →   │ # Cortex AI     │   →    │ ## vault-capture │
│ "Work with the  │      │ ## Commands     │        │ rules for...     │
│  Cortex vault"  │      │ ### search      │        │                  │
│                 │      │ ### capture     │        │ ## tier guide    │
│ ~20 tokens      │      │ ~3,000 tokens   │        │ ~1,000 tokens    │
└─────────────────┘      └─────────────────┘        └──────────────────┘
```

**What each stage reveals:**

| Stage | Content | Purpose | Token cost |
|-------|---------|---------|------------|
| 1. Summary | Skill name + description | "Does this skill exist? Is it relevant?" | ~20 |
| 2. Instructions | SKILL.md body | "How do I use this skill? What tools/commands?" | ~100-3,000 |
| 3. Knowledge | `reference.md` (vault notes) | "What domain knowledge does this skill need?" | ~500-2,000 |

**The pointer index bridges stages 1 and 3.** `core-context.md` always includes
an on-demand index that tells the agent which skills contain what knowledge
topics — without loading the knowledge itself. This is a ~200-token investment
that lets the agent reason about stage 3 content from stage 1:

```
Stage 1 (summary):  "homelab skill exists"
                      ↓
Pointer index:       "homelab skill has: Proxmox cluster, VLAN layout, Docker compose"
                      ↓
Stage 2 (skill):     SKILL.md loaded — agent knows commands/tools
                      ↓
Stage 3 (knowledge): reference.md read — agent gets the actual vault notes
```

**Agent-driven vs. user-driven disclosure.** This is progressive disclosure,
but with an important caveat: stages 2 and 3 are driven by the *agent's
judgment*, not the user's explicit navigation. The agent decides when a skill
is relevant (stage 2) and when vault knowledge is needed (stage 3). A classic
progressive disclosure UI would surface stage 3 content in the interface when
the user drills deeper; here, the agent does the drilling based on relevance
to the user's query. This is **agent-mediated progressive disclosure** — the
agent acts as the intermediary that decides how deep to go.

**Where it differs from standard progressive disclosure:**

- Standard: user clicks/drills → more detail appears
- Cortex: agent reasons about relevance → loads more context → answers better

The user doesn't see the intermediate stages. They ask a question, and the
agent transparently loads the appropriate depth of knowledge before responding.

## distill.py Implementation

### `sync_core_context()` — Eager path (`distill.py:479-533`)

```python
def sync_core_context(notes, cfg, eager_tiers, strip_links, dry):
    eager = [n for n in notes if n.tier in eager_tiers]
    # Concatenate core notes into core-context.md
    # Append on-demand pointer index for skill: and project tiers
    # Output: <vault>/_sync/distilled/opencode/core-context.md
```

### `sync_skill_embeds()` — Lazy path (`distill.py:536-572`)

```python
def sync_skill_embeds(notes, cfg, strip_links, dry):
    skills_dir = Path(cfg["skills_dir"])  # ~/.config/opencode/skills
    embed_name = cfg.get("embed_filename", "reference.md")
    by_skill = {}
    for n in notes:
        if n.tier.startswith("skill:"):
            by_skill[n.tier.split(":", 1)[1]].append(n)
    # For each skill, write concatenated note bodies to:
    #   skills/<name>/reference.md
    # Agent reads this file only when the skill is active
```

### Config (`cortex.yaml`)

```yaml
targets:
  core_context:
    type: core-context
    output_file: "<vault>/_sync/distilled/opencode/core-context.md"
    opencode_config: "~/.config/opencode/opencode.jsonc"

  skills:
    type: skill-embed
    skills_dir: "~/.config/opencode/skills"      # Where SKILL.md dirs live
    embed_filename: "reference.md"                # Generated lazy-load target
```

## MCP Server Auto-Reload (supporting mechanism)

The MCP server (`vault.ts`) doesn't directly participate in lazy loading, but
supports it by transparently reloading `memory.json` when distillation finishes:

```typescript
function getIndex(): VaultIndex {
  const mtime = statSync(_memoryJsonPath).mtimeMs;
  if (mtime > _loadedMtimeMs) loadIndex();  // auto-reload
  return _index;
}
```

This means `memory_write` → `fireDistill()` (background) → `memory.json`
updated → MCP server picks up changes on next query. No manual reload needed.

## Token Budget Analysis

| Component | Tokens | When loaded |
|-----------|--------|-------------|
| `<available_skills>` block | ~60 (3 skills × 20) | Every session |
| `core-context.md` | ~2,000-5,000 | Every session (via `instructions[]`) |
| `cortex-ai` SKILL.md | **~700** (was ~3,000) | Only on cortex operations |
| `homelab` SKILL.md | ~100 | Only on homelab topics |
| `sms` SKILL.md | ~300 | Only on SMS operations |
| `reference.md` (vault notes) | ~500-2,000/skill | Only when skill is active |

**Without lazy loading:** ~6,000+ tokens burned every session, regardless of
relevance.

**With lazy loading:** ~2,000-5,000 tokens for core context, then 0 additional
unless a skill is invoked. A homelab-only session never pays for cortex or SMS
instructions.

### SKILL.md Progressive Disclosure (applied)

The cortex-ai SKILL.md was reduced from **435 lines (~3,000 tokens)** to
**~100 lines (~700 tokens)** by applying the same progressive disclosure
principle used at the framework level:

| What | Before | After | Where it went |
|------|--------|-------|---------------|
| Core commands (search/get/add/capture/sync) | In SKILL.md | In SKILL.md | Kept — always needed |
| Advanced commands (version/status/uninstall/list) | In SKILL.md | Removed | Discoverable via `distill.py --help` |
| Import/purge/portfolio/open | In SKILL.md | Removed | Discoverable via `distill.py --help` |
| Hive operations | In SKILL.md | Removed | Discoverable via `distill.py --help` |
| Path resolution details | In SKILL.md | Condensed | 1-line pointer to `--show-config` |
| Tier guide | In SKILL.md | In SKILL.md | Kept — small, always useful |

**77% reduction** in SKILL.md size. The agent loads 700 tokens instead of 3,000
when a cortex operation is triggered. Advanced commands are still accessible —
the agent discovers them via `distill.py --help` or by reasoning about the
tool's capabilities.

## Design Principles

1. **Two boundaries, not one.** Skill instructions (SKILL.md) and vault
   knowledge (reference.md) are independently lazy. You can load a skill's
   instructions without loading its full knowledge base. This maps to the
   three-stage progressive disclosure model: summary → instructions → knowledge.

2. **Pointer index in eager context.** `core-context.md` always includes the
   on-demand index, so the agent knows what knowledge exists without loading it.
   This is a ~200-token investment that bridges stage 1 (summary) to stage 3
   (knowledge) without forcing the agent to load everything in between. Prevents
   "I don't know that exists" failures.

3. **Fire-and-forget distillation.** `memory_write` triggers background
   distillation. The MCP server auto-reloads on file change. No explicit sync
   step required for single writes.

4. **Idempotent builds.** `distill.py` only writes files whose content changed
   (hash comparison). Running it twice is safe and fast.

5. **Graceful degradation.** If a skill directory is missing,
   `sync_skill_embeds` prints a warning and skips. The system never fails hard
   on missing lazy targets.

## Limitations

- **SKILL.md is still atomic.** When `skill(name="cortex-ai")` is called, the
  full SKILL.md is injected. The 77% size reduction (435→100 lines) mitigates
  this, but there's no per-section loading within a skill. Advanced commands
  are discovered at runtime rather than pre-loaded.

- **reference.md is all-or-nothing.** All `skill:<name>` notes are concatenated
  into one file. No per-note lazy loading within a skill.

- **Pointer index is static.** The on-demand section in `core-context.md` is
  rebuilt on every distill, but doesn't adapt to usage patterns (e.g., "this
  user never uses the homelab skill").

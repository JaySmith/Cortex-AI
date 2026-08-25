# Graph Report - .  (2026-08-25)

## Corpus Check
- 84 files · ~52,017 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 949 nodes · 1663 edges · 85 communities (56 shown, 29 thin omitted)
- Extraction: 93% EXTRACTED · 7% INFERRED · 0% AMBIGUOUS · INFERRED: 109 edges (avg confidence: 0.69)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Encoder Core & Tests
- Agent Import Pipeline
- Hub/Hive Client
- Vault Data Model & Hive Sync
- CLI Main & Commands
- Install/Bootstrap Lifecycle
- Encoder Engine & Migrations
- Lint Rules (behavior)
- VaultNote Model & Tests
- Lint Test Suite
- Vault Templates & Init
- Platform Installer Base
- Memory Read Commands
- Memory Delete Tests
- Lint Check Functions
- Memory Write Tests
- Managed Block & OpenCode Install
- Install Context & Codex/Copilot
- Install Result & Uninstall
- Versioning & Bug Records
- Lint CLI Emitters
- OpenCode Installer Tests
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 60
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 67
- Community 68
- Community 74
- Community 75
- Community 76
- Community 77
- Community 78
- Community 79
- Community 80
- Community 81
- Community 82
- Community 83

## God Nodes (most connected - your core abstractions)
1. `VaultNote` - 69 edges
2. `InstallContext` - 32 edges
3. `HubClient` - 31 edges
4. `InstallResult` - 29 edges
5. `run_encode()` - 27 edges
6. `OpenCodeInstaller` - 24 edges
7. `TestVaultNote` - 23 edges
8. `run_lint()` - 22 edges
9. `InstallerBase` - 21 edges
10. `LintResult` - 19 edges

## Surprising Connections (you probably didn't know these)
- `TestExcluded` --uses--> `VaultNote`  [INFERRED]
  tests/test_encode.py → cortex/encoder/core.py
- `TestFindDrainedNotes` --uses--> `VaultNote`  [INFERRED]
  tests/test_encode.py → cortex/encoder/core.py
- `TestHiveEligible` --uses--> `VaultNote`  [INFERRED]
  tests/test_encode.py → cortex/encoder/core.py
- `TestLoadConfig` --uses--> `VaultNote`  [INFERRED]
  tests/test_encode.py → cortex/encoder/core.py
- `TestParseFrontmatter` --uses--> `VaultNote`  [INFERRED]
  tests/test_encode.py → cortex/encoder/core.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Two-Number Versioning & Upgrade Safety System** — changelog_release_version, changelog_schema_version, changelog_upgrade_safety, changelog_migrations_registry [EXTRACTED 1.00]
- **Encoder Tier-Routing Flow** — ext_scan_vault, ext_vaultnote, mm_tier_system, mm_encoding [INFERRED 0.85]
- **Hive Sync Flow (client + push/pull + eligibility)** — hive_hub_client_py, hive_push, hive_pull, hive_eligible, hive_conflict_resolution [EXTRACTED 1.00]
- **Cortex phased delivery plan (Phase 1-4)** — implementation_plans_cortex_phase_1_cli_installation_cli_consolidation, implementation_plans_cortex_phase_2_linting_ci_quality_gates, implementation_plans_cortex_phase_3_multi_agent_support_platform_agnostic, implementation_plans_cortex_phase_4_product_polish_product_experience [EXTRACTED 1.00]
- **Tier system routes notes to output targets** — docs_vault_schema_tier_routing, example_vault_knowledge_patterns_tiered_memory_tiered_memory_model, skills_cortex_ai_skill_tier_guide, docs_vault_note_schema_vault_note [INFERRED 0.85]
- **Observe-propose-learn capture with human approval** — skills_auto_learn_skill_observe_propose_learn, skills_auto_learn_skill_capturable_signals, skills_auto_learn_reference_noise_filters, skills_cortex_ai_skill_capture [INFERRED 0.85]

## Communities (85 total, 29 thin omitted)

### Community 0 - "Encoder Core & Tests"
Cohesion: 0.05
Nodes (19): hive_eligible(), parse_frontmatter(), Return True if all required keys are present; print error otherwise., Drop a note body's own leading `# Title` (redundant with encoder heading)., Drop a trailing `## Related` section (vault nav; dead weight in encoded context), Write content to path, skipping if content is already identical., strip_leading_h1(), strip_related_section() (+11 more)

### Community 1 - "Agent Import Pipeline"
Cohesion: 0.09
Nodes (24): backup_file(), build_note(), default_locations(), first_existing(), import_claude_memory(), import_markdown_file(), import_opencode_instructions(), main() (+16 more)

### Community 2 - "Hub/Hive Client"
Cohesion: 0.08
Nodes (20): HubClient, HubConnectionError, Any, Hive — lightweight MCP-over-HTTP client for cortex-hub.  Speaks the hub's Stream, Store a memory on the hub., Retrieve a memory by key., Search memories by content, key, or tags., Reconnect to the hub and retry the failed tool call. (+12 more)

### Community 3 - "Vault Data Model & Hive Sync"
Cohesion: 0.05
Nodes (45): Conflict Resolution (newest updated wins), Hub sync exclusion rules, Hub Key Format vault/{machine_id}/{note_id}, Hub Value (JSON) representation, machine_id field, Vault Note data model, cortex lint validation, Vault Directory Layout (+37 more)

### Community 4 - "CLI Main & Commands"
Cohesion: 0.09
Nodes (41): bootstrap(), _build_context(), config_get(), _config_set(), _cortex_config_dir(), _cortex_pointer(), delete(), doctor() (+33 more)

### Community 5 - "Install/Bootstrap Lifecycle"
Cohesion: 0.07
Nodes (34): cortex bootstrap, cortex install, cortex uninstall, Install manifest backup, Schema version guard (no downgrade), Consolidate scripts behind cortex CLI, Compatibility shims for legacy scripts, cortex install command (+26 more)

### Community 6 - "Encoder Engine & Migrations"
Cohesion: 0.16
Nodes (30): backup_sync_dir(), build_wiki_graph(), check_and_migrate(), cortex_version(), hive_pull(), hive_push(), hive_status(), load_config() (+22 more)

### Community 7 - "Lint Rules (behavior)"
Cohesion: 0.09
Nodes (17): Run all lint rules on a vault.      Returns a dict with keys: errors, warnings,, run_lint(), Test the run_lint function directly., Example vault only flags README.md (not a real note, missing frontmatter)., Detects notes without a type field., Detects notes without a tier field., Detects notes with unrecognized tier values., Detects notes without aliases. (+9 more)

### Community 9 - "Lint Test Suite"
Cohesion: 0.09
Nodes (19): lint_vault(), _make_bare_file(), _make_note(), _make_note_in_path(), Path, Tests for cortex lint — all rules and CLI integration., Create a note where the file stem differs from the id., Create a vault note with given frontmatter fields.      Use ``filename_suffix`` (+11 more)

### Community 10 - "Vault Templates & Init"
Cohesion: 0.14
Nodes (13): apply_template(), list_templates(), Path, Render a starter vault from a template name.  Templates live in subdirectories o, Return {name: description} for all available templates., Return {relative_path: content} for the named template.      Raises ``ValueError, Write the named template into *vault_path*.      Returns a list of relative path, render_template() (+5 more)

### Community 11 - "Platform Installer Base"
Cohesion: 0.13
Nodes (18): ABC, _add_platform_commands(), Register install/uninstall/status commands on a platform's Typer app., InstallerBase, Base classes for platform installers., Abstract base for platform installers., Return True if this platform appears to be installed or configured., Codex platform installer — Wave 1 stub. (+10 more)

### Community 12 - "Memory Read Commands"
Cohesion: 0.14
Nodes (20): _error(), _find_memory_json(), get(), init(), list_notes_cmd(), _load_memory_json(), _print_note(), Pretty-print a note dict from memory.json. (+12 more)

### Community 13 - "Memory Delete Tests"
Cohesion: 0.12
Nodes (12): _create_note_file(), Path, Patches existing note body with --update., Creating a note that already exists (without --update) raises error., Create a raw vault note .md file in the canonical type directory., --yes deletes the note file without prompting., Delete removes the note entry and its graph edges from memory.json., Deleting a note that does not exist raises an error. (+4 more)

### Community 14 - "Lint Check Functions"
Cohesion: 0.17
Nodes (15): _check_dangling_wiki_link(), _check_duplicate_id(), _check_empty_body(), _check_invalid_tier(), _check_missing_aliases(), _check_missing_id(), _check_missing_tier(), _check_missing_type() (+7 more)

### Community 15 - "Memory Write Tests"
Cohesion: 0.11
Nodes (10): Creates a note file with frontmatter when no --body., Creates a note file with body content., Reads body from a file., `entity` maps to entities/, not the buggy `entitys/`., A new note with --category lands in <type-dir>/<category>/., --update patches a note nested under <type>/<category>/ regardless of layout., --update on a non-existent note raises error., --no-encode skips the background encode. (+2 more)

### Community 16 - "Managed Block & OpenCode Install"
Cohesion: 0.15
Nodes (12): Wrap content in managed block markers., Replace or insert a managed block in existing file content.      If a managed bl, render_managed_block(), upsert_managed_block(), Install the cortex-ai skill into OpenCode's skills directory., example_vault_root(), install_ctx(), Tests for platform installers. (+4 more)

### Community 17 - "Install Context & Codex/Copilot"
Cohesion: 0.22
Nodes (6): InstallContext, Return a list of validation errors. Empty list means healthy., Everything an installer needs to do its work., CodexInstaller, CopilotInstaller, GitHub Copilot platform installer — Wave 1 stub.

### Community 18 - "Install Result & Uninstall"
Cohesion: 0.17
Nodes (6): InstallResult, Install Cortex assets for this platform. Returns what was done., Remove Cortex-managed assets for this platform., Summary of what an installer did (or would do in dry-run)., Remove the cortex-ai skill from OpenCode's skills directory., TestInstallResult

### Community 19 - "Versioning & Bug Records"
Cohesion: 0.15
Nodes (15): import_cmd handler (main.py), _find_vault() shared helper, Bug: cortex import writes to wrong vault, run_import (import_agent.py), VERSION / pyproject.toml / __init__.py version carriers, Bug: VERSION file out of sync with CHANGELOG, Release Discipline (bump at release time), Release Version (SemVer, VERSION file) (+7 more)

### Community 20 - "Lint CLI Emitters"
Cohesion: 0.16
Nodes (13): Context, _emit_human(), _emit_json(), lint_cmd(), list_rules(), _list_rules_cmd(), Any, Return registered rule metadata. (+5 more)

### Community 21 - "OpenCode Installer Tests"
Cohesion: 0.22
Nodes (4): OpenCodeInstaller, True if ~/.config/opencode/ exists., Check that the skill file exists and contains a managed block., TestOpenCodeInstaller

### Community 22 - "Community 22"
Cohesion: 0.18
Nodes (14): cortex doctor, sync_core_context(), Memory Model, Note Types (knowledge/entity/feedback/decision/session/log), The Tier System, The Vault (Obsidian-style Markdown), Vault-Only Notes, The Build Pipeline (encoder) (+6 more)

### Community 23 - "Community 23"
Cohesion: 0.21
Nodes (13): Postgres Full-Text Search (tsvector/tsquery), pgvector Semantic Search, Postgres + Link Graph for Hub Vault (ADR-0001), Recursive CTE Link Traversal, Agent (persona: human + AI pair), Cortex Hub Knowledge Model, Hub Vault (Postgres-backed shared store), Ingestion Pipeline (+5 more)

### Community 24 - "Community 24"
Cohesion: 0.17
Nodes (13): MIGRATIONS Registry, Upgrade-Safety Check, cortex encode, Bearer Token Auth (Phase 7, cortex-hub), Conflict Resolution (newest updated wins), hive_eligible() tier/frontmatter gate, Python HubClient (cortex/hub/client.py), MCP-over-HTTP Protocol (hub_memory_* tools) (+5 more)

### Community 25 - "Community 25"
Cohesion: 0.38
Nodes (11): delete_created(), find_manifests(), main(), process_manifest(), purge_encoded(), Path, Run the uninstall operation. Returns exit code (0 = ok)., Return all manifest.json files under _sync/backups, newest-name last. (+3 more)

### Community 26 - "Community 26"
Cohesion: 0.27
Nodes (3): Replace [[link]] and [[link|label]] with display text., strip_wiki_links(), TestStripWikiLinks

### Community 27 - "Community 27"
Cohesion: 0.17
Nodes (7): Test that import finds the vault correctly via _find_vault()., Vault named 'cortex-ai' under home is found., When CWD is the vault, _find_vault returns CWD., When no vault exists anywhere, _find_vault returns CWD., cortex import --dry-run resolves vault named 'cortex-ai' and does not error., cortex import with no vault anywhere errors, not silently writes to CWD., TestVaultAutoDetection

### Community 28 - "Community 28"
Cohesion: 0.20
Nodes (11): _apply_fixes(), _find_vault_path(), _fix_missing_aliases(), _fix_missing_field(), _fix_non_slug_id(), Path, Apply auto-fixes for fixable issues., Add a missing frontmatter field with a default value. (+3 more)

### Community 29 - "Community 29"
Cohesion: 0.22
Nodes (11): _backup_file(), install(), Snapshot a file into backup_dir. Returns the backup path, or None if     the sou, Re-encode memory and refresh Cortex assets.      Default is dry-run (preview onl, Bootstrap or upgrade Cortex for a user.      Handles everything: venv deps, conf, Print Cortex version information., upgrade(), version() (+3 more)

### Community 30 - "Community 30"
Cohesion: 0.18
Nodes (11): _build_note_content(), Write a memory note to the vault. Without --body/--body-file, writes frontmatter, Read body content from inline text or file., Build markdown content with YAML frontmatter and optional body., Map a note type to its canonical top-level directory name., Resolve where a note lives (for update) or should be created (for new).      Ret, _read_body(), _record_action() (+3 more)

### Community 31 - "Community 31"
Cohesion: 0.18
Nodes (6): Tests for cortex doctor command., Doctor reports healthy when all pieces exist., Doctor reports issues when pieces are missing., Doctor with --platform checks only that platform., Doctor with unknown platform exits with error., TestDoctor

### Community 32 - "Community 32"
Cohesion: 0.24
Nodes (5): Path, Tests for cortex doctor diagnostics., TestDoctorHealthy, TestDoctorNeedsAttention, TestDoctorSpecificPlatform

### Community 33 - "Community 33"
Cohesion: 0.27
Nodes (4): Path, Tests for structured error messages across the CLI., TestErrorMessages, TestUpgradeErrors

### Community 34 - "Community 34"
Cohesion: 0.24
Nodes (7): Tests for CLI memory commands — get, write, search., Write a memory.json into the vault's encoded directory., Search returns matching notes., Search returns empty results., Search ranks by relevance and returns top results., TestMemorySearch, _write_memory_json()

### Community 35 - "Community 35"
Cohesion: 0.18
Nodes (6): Respects --vault flag., Fails cleanly when no vault or memory.json is available., Returns full note content + metadata from memory.json., Returns error for missing note., Falls back to vault file scan when not in memory.json., TestMemoryGet

### Community 36 - "Community 36"
Cohesion: 0.27
Nodes (4): Path, Tests for cortex upgrade command., TestUpgradeApply, TestUpgradePreview

### Community 37 - "Community 37"
Cohesion: 0.31
Nodes (9): cortex memory get (CLI), cortex memory search (CLI), cortex memory get, cortex memory related, cortex memory search, cortex memory think, cortex-ai Skill, Related Scoring (tags/category/type/wiki-link graph) (+1 more)

### Community 38 - "Community 38"
Cohesion: 0.28
Nodes (8): Inline update of memory.json after a write — no full encode needed.      Upserts, _update_memory_json_inline(), extract_wiki_links(), Extract target ids from [[wiki-link]] syntax in a note body., Parse [[wiki-links]] from all note bodies and resolve them.      Parameters, Resolve a single wiki-link target to a note id, or None., _resolve_single_link(), resolve_wiki_links()

### Community 39 - "Community 39"
Cohesion: 0.31
Nodes (5): Show basic health of the Cortex installation., status(), Return the schema version recorded in the vault's memory.json, or None., read_vault_schema(), TestReadVaultSchema

### Community 40 - "Community 40"
Cohesion: 0.32
Nodes (8): Reverting via Install Manifests, cortex bootstrap, cortex install, cortex uninstall, The Dev Loop (edit repo -> dry-run -> upgrade), Installation Guide, Install Manifest (backups), Quick Start (five commands)

### Community 41 - "Community 41"
Cohesion: 0.29
Nodes (6): Custom Sync Target, Encoder Flow (scan_vault -> sync targets), scan_vault(), VaultNote object, write_file() helper (dry-run aware), hive Frontmatter Field (VaultNote.hive)

### Community 42 - "Community 42"
Cohesion: 0.33
Nodes (7): cortex memory write (CLI), capture flow, cortex memory write, Learnings.md scratch file, sync (capture-then-rebuild-then-drain), Capture-Then-Rebuild Workflow, Encoding (tier routing)

### Community 43 - "Community 43"
Cohesion: 0.33
Nodes (7): Quality Checks (ruff/mypy/pytest), MyPy Type Check Step, CI Pipeline (GitHub Actions), Ruff Check Step, Ruff Format Check Step, Pytest Step, Ruff Pre-commit Hook

### Community 44 - "Community 44"
Cohesion: 0.33
Nodes (5): load_config(), Any, Path, Config loading for the Cortex vault.  Shared by the encoder and CLI commands. Lo, Load and return a cortex.yaml config dict. Exits on error.

### Community 47 - "Community 47"
Cohesion: 0.47
Nodes (3): extract_managed_block(), Extract the content between managed block markers. Returns None if absent., TestExtractManagedBlock

### Community 48 - "Community 48"
Cohesion: 0.33
Nodes (5): Shared fixtures for cortex-ai tests., Copy example-vault into a temporary directory and return its path., Scan the copied example-vault and return the note list., vault(), vault_notes()

### Community 49 - "Community 49"
Cohesion: 0.40
Nodes (3): Path, Backup a file before modifying it. Returns backup path or None., Write a file, respecting dry_run. Returns True if file changed.

### Community 50 - "Community 50"
Cohesion: 0.40
Nodes (5): Hive Integration Plan (cortex-ai + cortex-hub), cortex-hub (nervous system), CLI Memory Commands, Cortex (tiered memory for AI agents), Cortex-Hub (multi-agent coordination layer)

### Community 51 - "Community 51"
Cohesion: 0.67
Nodes (3): Live Install (deployment target), Repo Is Source of Truth (not live install), Repo vs Live Install Distinction

### Community 56 - "Community 56"
Cohesion: 0.67
Nodes (3): cortex doctor, cortex doctor diagnostics, cortex doctor enhancements

## Knowledge Gaps
- **64 isolated node(s):** `cortex-ai`, `Ruff Format Check Step`, `MyPy Type Check Step`, `Pytest Step`, `File Sanity Pre-commit Hooks` (+59 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **29 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `InstallContext` connect `Install Context & Codex/Copilot` to `CLI Main & Commands`, `Platform Installer Base`, `Community 47`, `Managed Block & OpenCode Install`, `Community 49`, `Install Result & Uninstall`, `OpenCode Installer Tests`?**
  _High betweenness centrality (0.115) - this node is a cross-community bridge._
- **Why does `VaultNote` connect `VaultNote Model & Tests` to `Encoder Core & Tests`, `Hub/Hive Client`, `Encoder Engine & Migrations`, `Community 39`, `Community 45`, `Community 46`, `Lint Check Functions`, `Community 26`, `Community 28`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **Why does `HubClient` connect `Hub/Hive Client` to `VaultNote Model & Tests`, `Encoder Engine & Migrations`?**
  _High betweenness centrality (0.049) - this node is a cross-community bridge._
- **Are the 16 inferred relationships involving `VaultNote` (e.g. with `LintResult` and `HubClient`) actually correct?**
  _`VaultNote` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `InstallContext` (e.g. with `CodexInstaller` and `CopilotInstaller`) actually correct?**
  _`InstallContext` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 5 inferred relationships involving `HubClient` (e.g. with `VaultNote` and `TestHeaders`) actually correct?**
  _`HubClient` has 5 INFERRED edges - model-reasoned connections that need verification._
- **Are the 8 inferred relationships involving `InstallResult` (e.g. with `CodexInstaller` and `CopilotInstaller`) actually correct?**
  _`InstallResult` has 8 INFERRED edges - model-reasoned connections that need verification._
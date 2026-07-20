# Cortex Phase 4 — Product Experience & Graphify-Level Polish

## Agent Implementation Brief

### Objective
Turn Cortex from a useful tool into a polished product experience that new users can understand quickly, install confidently, and operate safely.

This phase focuses on onboarding, diagnostics, upgrades, documentation, templates, and user trust.

---

## Background

After Phases 1–3, Cortex should have:

- A product-grade CLI.
- Linting, formatting, tests, and CI.
- Multi-agent installation support.

Phase 4 improves the experience around those capabilities so users can self-serve successfully.

---

## Scope

### In Scope

- New documentation structure.
- Quickstart experience.
- `cortex doctor` improvements.
- `cortex upgrade` command.
- `cortex init` starter vault templates.
- Local-only usage metadata.
- Improved error messages.
- Product-style README refresh.

### Out of Scope

- Hosted SaaS backend.
- Telemetry or remote analytics.
- Enterprise admin portal.
- Major MCP protocol redesign.

---

## Product Principles

Cortex should feel like this:

```text
Install
Initialize
Remember
Query
Trust
```

The user should not need to understand schema versions, MCP internals, sync folders, or distillation architecture during first use.

---

## Documentation Structure

Create or reorganize documentation:

```text
docs/
  overview.md
  quickstart.md
  installation.md
  cli-reference.md
  memory-model.md
  vault-schema.md
  architecture.md
  troubleshooting.md
  migration.md
  development.md
```

### README.md Structure

Refresh README to follow this flow:

```text
1. What Cortex is
2. Why it matters
3. Install in one command
4. Quickstart
5. Common commands
6. How memory works at a high level
7. Supported agents
8. Links to advanced docs
```

Keep the top of README focused and short.

---

## Quickstart Requirements

Create:

```text
docs/quickstart.md
```

The quickstart should include only the minimum productive path:

```bash
uv tool install cortex-ai
cortex init
cortex install
cortex status
```

Do not lead with advanced schema, migrations, or MCP details.

The quickstart should include:

- Prerequisites.
- Install command.
- Initialize a starter vault.
- Install into an agent.
- Verify health.
- First memory write.
- First memory search.

Example:

```bash
cortex memory write --title "Preferred style" --tier core --type feedback
cortex memory search "Preferred style"
```

---

## `cortex doctor` Enhancements

If Phase 3 introduced `cortex doctor`, expand it here.

Required checks:

```text
Python version
Node version if MCP build requires Node
Cortex package version
Config path
Vault path
Vault write permissions
Schema version
Distilled output freshness
Memory file validity
MCP server build
Agent integration files
Managed config blocks
Backup availability
```

Output should be actionable.

Healthy example:

```text
Cortex doctor

Core
✓ Python version supported
✓ Config found
✓ Vault writable
✓ Schema compatible
✓ Distilled memory current

MCP
✓ Server built
✓ Memory file readable

Agent integrations
✓ OpenCode configured

Status: HEALTHY
```

Unhealthy example:

```text
✗ Distilled memory is missing
Suggested fix: cortex distill
```

---

## `cortex upgrade`

Implement an upgrade command for live installations.

Responsibilities:

1. Detect current install.
2. Create backup.
3. Check schema compatibility.
4. Apply migrations if required.
5. Rebuild MCP server if required.
6. Re-run distillation.
7. Re-validate with doctor checks.
8. Print summary.

UX:

```bash
cortex upgrade
cortex upgrade --dry-run
cortex upgrade --apply
```

Dry-run should be the safe default if upgrade will modify multiple files.

Example output:

```text
Cortex upgrade preview

Would backup: /path/to/vault/_sync
Would migrate schema: 2 -> 3
Would rebuild MCP server
Would re-distill memory

Run cortex upgrade --apply to apply changes.
```

---

## `cortex init` Starter Vaults

Add starter templates:

```text
Personal
Engineering
Product Management
Knowledge Base
```

Command:

```bash
cortex init
cortex init --template engineering
cortex init --template product-management
```

Generated example structure:

```text
vault/
  core/
    preferences.md
    working-style.md
  projects/
    example-project.md
  decisions/
    example-decision.md
  feedback/
    example-feedback.md
  sessions/
    example-session.md
```

Each template should include valid frontmatter and comments explaining what belongs in the note.

---

## Local-Only Usage Metadata

Add optional local-only metadata stored inside the vault sync area.

Possible file:

```text
<vault>/_sync/metrics.json
```

Track only local operational metadata:

```json
{
  "memory_count": 42,
  "last_distill_duration_ms": 781,
  "last_distill_at": "2026-07-20T09:23:00-05:00",
  "vault_size_bytes": 1234567
}
```

Requirements:

- No telemetry.
- No network calls.
- No user content sent anywhere.
- Document clearly that metrics are local only.

---

## Error Message Standards

All user-facing errors should follow this pattern:

```text
What failed:
  Config file not found.

Why it matters:
  Cortex needs the config to locate your vault and distilled memory.

Suggested fix:
  Run cortex install or pass --config /path/to/cortex.yaml.
```

Apply this pattern to:

- Missing config.
- Missing vault.
- Invalid schema.
- Failed MCP build.
- Missing platform config.
- Distillation failure.

---

## Product README Improvements

Add concise examples:

```bash
cortex status
cortex memory search "release preferences"
cortex memory write --title "Review preference" --tier core
cortex doctor
```

Add a short positioning statement:

```text
Cortex gives AI coding agents durable memory across sessions by distilling a local vault into agent-ready context and serving it through MCP.
```

Add a short comparison:

```text
Use Cortex for durable agent memory.
Use code graph tools for repository structure.
Use both together for context-aware coding agents.
```

---

## Tests

Add tests for:

```text
tests/test_init_templates.py
tests/test_upgrade.py
tests/test_doctor_diagnostics.py
tests/test_error_messages.py
```

Minimum coverage:

- `cortex init` creates valid starter vault.
- Each template contains valid frontmatter.
- `cortex doctor` returns healthy for valid fixture.
- `cortex doctor` gives suggested fix for missing memory.
- `cortex upgrade --dry-run` writes nothing.
- `cortex upgrade --apply` creates backup and revalidates.
- Error messages include what failed, why it matters, and suggested fix.

---

## Acceptance Criteria

This phase is complete when:

```bash
cortex init --template engineering
cortex install
cortex status
cortex doctor
cortex upgrade --dry-run
```

all work cleanly.

Documentation exists for:

```text
quickstart
installation
CLI reference
memory model
troubleshooting
migration
development
```

A new user can understand the value and basic usage from the README and quickstart without needing to read architecture docs.

---

## Done Definition

This phase is done when Cortex has a polished onboarding and operating experience: clear docs, safe upgrades, useful diagnostics, starter templates, and actionable errors that make the product easy to adopt and hard to misuse.

# Cortex Phase 3 — Multi-Agent Platform Support

## Agent Implementation Brief

### Objective

Make Cortex platform agnostic by adding dedicated installation workflows for major AI coding assistants.

The goal is for a user to install Cortex into their preferred assistant with a single platform-specific command.

Example target commands:

```bash
cortex opencode install
cortex claude install
cortex codex install
cortex copilot install
```

---

## Background

Cortex provides persistent memory and MCP-based access for coding agents. To
drive adoption, Cortex should reduce platform-specific setup friction and
generate the right files/configuration for each supported assistant.

This phase builds on Phase 1 CLI work and Phase 2 quality gates.

---

## Scope

### In Scope

- Create an installer framework.
- Implement Wave 1 agent installers.
- Add platform-specific config generation.
- Add validation for installed platforms.
- Add uninstall support for platform-installed assets.
- Add tests for generated config files.

### Out of Scope

- Hosted sync service.
- UI application.
- Enterprise deployment tooling.
- Full support for every assistant in the ecosystem.

---

## Target Platforms

### Wave 1 — full implementation

```text
OpenCode
```

### Wave 1 — framework stubs

Register in the framework with a working `detect()` and an `install()` skeleton,
but only minimal asset generation:

```text
Codex
GitHub Copilot
```

### Wave 2

Prepare extensible framework for:

```text
Claude Code   (moved from Wave 1 — uses CLAUDE.md / ~/.claude flat files, not MCP JSON)
Cursor
Gemini CLI
Aider
Kilo
```

Wave 2 does not need to be implemented in this phase. Claude Code is deferred to
Wave 2 because its integration model (CLAUDE.md + flat memory files) differs
enough from OpenCode's (MCP + skills) to warrant proving the framework on
OpenCode first.

---

## Desired User Experience

Generic install:

```bash
cortex install
```

Platform-specific install:

```bash
cortex opencode install
cortex claude install
cortex codex install
cortex copilot install
```

Platform-specific uninstall:

```bash
cortex opencode uninstall
cortex claude uninstall
```

Validation:

```bash
cortex doctor
cortex doctor --platform opencode
```

---

## Installer Architecture

Create a platform installer abstraction:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

@dataclass
class InstallContext:
    repo_root: Path
    vault_root: Path
    config_path: Path
    mcp_server_path: Path
    skills_dir: Path | None = None
    dry_run: bool = False

class InstallerBase(ABC):
    platform_name: str

    @abstractmethod
    def detect(self) -> bool:
        """Return True if this platform appears to be installed or configured."""

    @abstractmethod
    def install(self, context: InstallContext) -> None:
        """Install Cortex assets for this platform."""

    @abstractmethod
    def uninstall(self, context: InstallContext) -> None:
        """Remove Cortex-managed assets for this platform."""

    @abstractmethod
    def validate(self, context: InstallContext) -> list[str]:
        """Return a list of validation errors. Empty list means healthy."""
```

Implement concrete installers:

```text
cortex/platforms/opencode.py   (full)
cortex/platforms/codex.py      (stub — detect + install skeleton)
cortex/platforms/copilot.py    (stub — detect + install skeleton)
```

Claude Code (`cortex/platforms/claude.py`) is deferred to Wave 2.

### `detect()` logic per platform

`detect()` returns `True` when the platform's config directory exists:

| Platform    | `detect()` returns `True` when | Wave     |
|-------------|--------------------------------|----------|
| OpenCode    | `~/.config/opencode/` exists   | 1 (full) |
| Codex       | `~/.codex/` exists             | 1 (stub) |
| Copilot     | `~/.github-copilot/` exists    | 1 (stub) |
| Claude Code | `~/.claude/` exists            | 2        |

---

## Generated Assets

Each installer should generate only the files required for that platform.

Possible asset types:

```text
Agent instructions
Skill files
Command files
MCP server registration
Environment variable references
Project-local config
User-global config
```

Managed-content strategy depends on file format:

- **Markdown files** (skills, agent instructions) use comment markers:

  ```text
  <!-- BEGIN CORTEX MANAGED BLOCK -->
  ...
  <!-- END CORTEX MANAGED BLOCK -->
  ```

- **JSONC files** (`opencode.jsonc`) are managed via the surgical upsert logic
  ported in Phase 1 (`cortex/mcp/upsert.py`, from `cortex-mcp-upsert.py`). No
  comment markers are used — the upsert identifies the Cortex entry by its key
  name (`mcp.cortex`) and replaces only that block, preserving all comments and
  user content. Reuse this; do not hand-roll JSON markers.

This makes uninstall and upgrades safer.

### OpenCode installer — generated assets

The OpenCode installer (Wave 1, full) generates exactly what `setup.sh` does today:

1. MCP entry in `~/.config/opencode/opencode.jsonc` — via `cortex/mcp/upsert.py`
   (surgical, comment-preserving, no markers).
2. `~/.config/opencode/skills/cortex-ai/SKILL.md` — Markdown with the managed-block
   markers above.

---

## Safety Requirements

Installers must not overwrite user files blindly.

Required behavior:

1. Read existing file if present.
2. Preserve user-managed content.
3. Insert or update only the Cortex-managed block.
4. Create a backup before modifying existing files.
5. Support dry-run mode.
6. Print a summary of changed files.

Expected dry run:

```bash
cortex opencode install --dry-run
```

Example output:

```text
Would update: ~/.config/opencode/opencode.jsonc
Would create: ~/.config/opencode/skills/cortex-ai/SKILL.md
Would backup: ~/.config/opencode/opencode.jsonc
```

---

## `cortex doctor`

Add a diagnostic command that validates all installed platforms.

Checks:

```text
Cortex config exists
Vault exists
Distilled memory exists
MCP server build exists
Platform config exists
Platform contains Cortex-managed block
Required environment variables are present
Skill files exist where expected
```

Expected output:

```text
Cortex doctor

Core
✓ Config found
✓ Vault found
✓ Distilled memory found

OpenCode
✓ Config contains Cortex MCP server
✓ Cortex skill installed

Status: HEALTHY
```

If unhealthy:

```text
✗ OpenCode config missing Cortex MCP server
Suggested fix: cortex opencode install
```

---

## CLI Commands to Add

Add these command groups:

```bash
cortex opencode install
cortex opencode uninstall
cortex opencode status

cortex codex install
cortex codex uninstall
cortex codex status

cortex copilot install
cortex copilot uninstall
cortex copilot status

cortex doctor
```

`cortex claude *` commands are deferred to Wave 2.

---

## Tests

Create tests for:

```text
tests/test_platform_installers.py
tests/test_doctor.py
```

Minimum coverage:

- Installer does not overwrite unmanaged content.
- Installer adds managed block.
- Installer updates existing managed block.
- Installer creates backup.
- Dry-run does not write files.
- Uninstall removes managed block only.
- Doctor reports healthy fixture install.
- Doctor reports actionable fix for broken fixture install.

---

## Acceptance Criteria

Phase is complete when:

```bash
cortex opencode install --dry-run
cortex codex install --dry-run
cortex copilot install --dry-run
cortex doctor
pytest
```

all run successfully. (Claude Code dry-run is a Wave 2 criterion, not required here.)

For the OpenCode installer (Wave 1, full):

- Install command exists and generates the MCP entry + skill file.
- Uninstall command exists and removes only Cortex-managed content.
- Status command exists.
- Dry-run is supported.
- Tests validate generated files.

For the Codex and Copilot stubs:

- `detect()` and an `install()` skeleton exist and run under `--dry-run`.
- Full asset generation is not required in this phase.

---

## Done Definition

This phase is done when Cortex can install, uninstall, and validate its
integration with multiple AI coding assistants through dedicated platform
commands and safe generated configuration.

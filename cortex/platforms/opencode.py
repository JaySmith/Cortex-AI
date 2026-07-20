"""OpenCode platform installer — Wave 1 (full)."""

from __future__ import annotations

from pathlib import Path

from cortex.platforms.base import (
    InstallContext,
    InstallerBase,
    InstallResult,
    upsert_managed_block,
)

# Where OpenCode looks for skills
OPENCODE_CONFIG_DIR = Path.home() / ".config" / "opencode"
OPENCODE_SKILLS_DIR = OPENCODE_CONFIG_DIR / "skills"


class OpenCodeInstaller(InstallerBase):
    platform_name = "opencode"
    description = "OpenCode — AI coding assistant with CLI + skills"

    def detect(self) -> bool:
        """True if ~/.config/opencode/ exists."""
        return OPENCODE_CONFIG_DIR.is_dir()

    def install(self, context: InstallContext) -> InstallResult:
        """Install the cortex-ai skill into OpenCode's skills directory."""
        result = InstallResult()
        skills_dir = context.skills_dir or OPENCODE_SKILLS_DIR
        skill_dir = skills_dir / "cortex-ai"
        skill_file = skill_dir / "SKILL.md"

        # Read the template from the repo
        template_path = context.repo_root / "skills" / "cortex-ai" / "SKILL.md"
        if not template_path.exists():
            raise FileNotFoundError(f"Skill template not found: {template_path}")

        template = template_path.read_text(encoding="utf-8")

        # Replace <CORTEX_HOME> with the actual vault _sync path
        cortex_home = context.vault_root / "_sync"
        rendered = template.replace("<CORTEX_HOME>", str(cortex_home))

        # Wrap in managed block markers for safe upgrades
        managed_content = upsert_managed_block("", rendered)

        # Backup existing skill file if present
        if skill_file.exists():
            backup = self._backup(skill_file, context)
            if backup:
                result.backed_up.append(backup)

        # Write — use upsert to preserve user content outside the managed block
        if context.dry_run:
            if not skill_file.exists():
                result.created.append(skill_file)
            else:
                existing = skill_file.read_text(encoding="utf-8")
                if existing != managed_content:
                    result.updated.append(skill_file)
        else:
            skill_dir.mkdir(parents=True, exist_ok=True)
            if skill_file.exists():
                existing = skill_file.read_text(encoding="utf-8")
                final = upsert_managed_block(existing, rendered)
                if existing != final:
                    skill_file.write_text(final, encoding="utf-8")
                    result.updated.append(skill_file)
            else:
                skill_file.write_text(managed_content, encoding="utf-8")
                result.created.append(skill_file)

        return result

    def uninstall(self, context: InstallContext) -> InstallResult:
        """Remove the cortex-ai skill from OpenCode's skills directory."""
        result = InstallResult()
        skills_dir = context.skills_dir or OPENCODE_SKILLS_DIR
        skill_dir = skills_dir / "cortex-ai"
        skill_file = skill_dir / "SKILL.md"

        if skill_file.exists():
            backup = self._backup(skill_file, context)
            if backup:
                result.backed_up.append(backup)
            if not context.dry_run:
                skill_file.unlink()
                # Remove the directory if empty
                if not any(skill_dir.iterdir()):
                    skill_dir.rmdir()
            result.removed.append(skill_file)

        return result

    def validate(self, context: InstallContext) -> list[str]:
        """Check that the skill file exists and contains a managed block."""
        errors: list[str] = []
        skills_dir = context.skills_dir or OPENCODE_SKILLS_DIR
        skill_file = skills_dir / "cortex-ai" / "SKILL.md"

        if not skill_file.exists():
            errors.append(f"Skill file missing: {skill_file}")
            return errors

        content = skill_file.read_text(encoding="utf-8")
        if "BEGIN CORTEX MANAGED BLOCK" not in content:
            errors.append(f"Skill file exists but is not managed by Cortex: {skill_file}")

        # Check that <CORTEX_HOME> was resolved
        if "<CORTEX_HOME>" in content:
            errors.append("Skill file contains unresolved <CORTEX_HOME> placeholder")

        return errors

"""OpenCode platform installer — Wave 1 (full)."""

from __future__ import annotations

from pathlib import Path

from cortex.platforms.base import (
    InstallContext,
    InstallerBase,
    InstallResult,
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

        # OpenCode requires SKILL.md to START with YAML frontmatter
        # (https://opencode.ai/docs/skills), so the file is written raw — the
        # whole file is Cortex-managed and replaced wholesale on upgrade. Do
        # NOT wrap in a managed-block comment: a leading comment pushes the
        # frontmatter off the first line and the skill fails to load.
        existed = skill_file.exists()

        if context.dry_run:
            if not existed:
                result.created.append(skill_file)
            elif skill_file.read_text(encoding="utf-8") != rendered:
                result.updated.append(skill_file)
            return result

        # Backup existing skill file before overwriting
        if existed:
            backup = self._backup(skill_file, context)
            if backup:
                result.backed_up.append(backup)

        skill_dir.mkdir(parents=True, exist_ok=True)
        if existed:
            if skill_file.read_text(encoding="utf-8") != rendered:
                skill_file.write_text(rendered, encoding="utf-8")
                result.updated.append(skill_file)
        else:
            skill_file.write_text(rendered, encoding="utf-8")
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
        """Check that the skill file exists and is a loadable OpenCode skill.

        OpenCode requires SKILL.md to START with YAML frontmatter
        (https://opencode.ai/docs/skills), so the file is written raw with no
        managed-block wrapper. Validation therefore checks the real loading
        contract: the file exists, starts with frontmatter, and has no
        unresolved template placeholder.
        """
        errors: list[str] = []
        skills_dir = context.skills_dir or OPENCODE_SKILLS_DIR
        skill_file = skills_dir / "cortex-ai" / "SKILL.md"

        if not skill_file.exists():
            errors.append(f"Skill file missing: {skill_file}")
            return errors

        content = skill_file.read_text(encoding="utf-8")

        # OpenCode requires frontmatter as the very first line.
        if not content.lstrip("\ufeff").startswith("---"):
            errors.append(
                f"Skill file must start with YAML frontmatter (---): {skill_file}"
            )

        # Check that <CORTEX_HOME> was resolved
        if "<CORTEX_HOME>" in content:
            errors.append("Skill file contains unresolved <CORTEX_HOME> placeholder")

        return errors

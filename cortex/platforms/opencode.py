"""OpenCode platform installer — Wave 1 (full)."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from cortex.platforms.base import (
    InstallContext,
    InstallerBase,
    InstallResult,
)

# Where OpenCode looks for skills and config
OPENCODE_CONFIG_DIR = Path.home() / ".config" / "opencode"
OPENCODE_SKILLS_DIR = OPENCODE_CONFIG_DIR / "skills"

# The path that gets added to opencode.json's instructions array.
# Must match what OpenCode resolves at runtime — absolute path is unambiguous.
_AGENTS_INSTRUCTIONS_PATH = str(OPENCODE_SKILLS_DIR / "cortex-ai" / "AGENTS.md")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_jsonc(text: str) -> str:
    """Remove // line comments and /* */ block comments so json.loads can parse."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"(^|\s)//[^\n]*", r"\1", text)
    return text


def _find_opencode_config(config_dir: Path) -> Path | None:
    """Return the path to opencode.json or opencode.jsonc, or None."""
    for name in ("opencode.json", "opencode.jsonc"):
        p = config_dir / name
        if p.exists():
            return p
    return None


def _read_opencode_config(path: Path) -> dict | None:
    """Parse opencode.json/jsonc, returning the dict or None on failure."""
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".jsonc":
            text = _strip_jsonc(text)
        return json.loads(text)
    except (json.JSONDecodeError, OSError):
        return None


def _write_opencode_config(path: Path, data: dict) -> None:
    """Write the config back, preserving the original format."""
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _update_opencode_instructions(
    config_dir: Path,
    path_to_add: str | None,
    path_to_remove: str | None,
    dry: bool,
) -> bool:
    """Add or remove a path from opencode.json's instructions array.

    Returns True if the config was modified (or would be in dry-run).
    """
    config_path = _find_opencode_config(config_dir)
    if config_path is None:
        return False

    data = _read_opencode_config(config_path)
    if data is None:
        return False

    instructions = data.get("instructions")
    if not isinstance(instructions, list):
        instructions = []

    changed = False

    if path_to_add and path_to_add not in instructions:
        instructions.append(path_to_add)
        data["instructions"] = instructions
        changed = True

    if path_to_remove and path_to_remove in instructions:
        instructions.remove(path_to_remove)
        data["instructions"] = instructions
        changed = True

    if changed and not dry:
        _write_opencode_config(config_path, data)

    return changed


# ---------------------------------------------------------------------------
# Installer
# ---------------------------------------------------------------------------


class OpenCodeInstaller(InstallerBase):
    platform_name = "opencode"
    description = "OpenCode — AI coding assistant with CLI + skills"

    def detect(self) -> bool:
        """True if ~/.config/opencode/ exists."""
        return OPENCODE_CONFIG_DIR.is_dir()

    def install(self, context: InstallContext) -> InstallResult:
        """Install the cortex-ai skill, AGENTS.md, custom tools, and npm deps."""
        result = InstallResult()
        skills_dir = context.skills_dir or OPENCODE_SKILLS_DIR
        config_dir = skills_dir.parent
        skill_dir = skills_dir / "cortex-ai"
        skill_file = skill_dir / "SKILL.md"

        # ---- 1. SKILL.md (template-rendered) ----
        template_path = context.repo_root / "skills" / "cortex-ai" / "SKILL.md"
        if not template_path.exists():
            raise FileNotFoundError(f"Skill template not found: {template_path}")

        template = template_path.read_text(encoding="utf-8")
        cortex_home = context.vault_root / "_sync"
        rendered = template.replace("<CORTEX_HOME>", str(cortex_home))

        existed = skill_file.exists()

        if context.dry_run:
            if not existed:
                result.created.append(skill_file)
            elif skill_file.read_text(encoding="utf-8") != rendered:
                result.updated.append(skill_file)
        else:
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

        # ---- 2. AGENTS.md (static copy to skills dir) ----
        agents_src = context.repo_root / "opencode" / "AGENTS.md"
        agents_dst = skill_dir / "AGENTS.md"
        if agents_src.exists():
            self._install_static_file(agents_src, agents_dst, result, context)

        # ---- 3. tools/cortex.ts (static copy) ----
        tools_src = context.repo_root / "opencode" / "tools" / "cortex.ts"
        tools_dst = config_dir / "tools" / "cortex.ts"
        if tools_src.exists():
            self._install_static_file(tools_src, tools_dst, result, context)

        # ---- 4. package.json (merge or create) ----
        pkg_src = context.repo_root / "opencode" / "package.json"
        pkg_dst = config_dir / "package.json"
        if pkg_src.exists():
            self._install_package_json(pkg_src, pkg_dst, result, context)

        # ---- 5. npm install (install tool dependencies) ----
        if not context.dry_run:
            self._run_npm_install(config_dir, result)

        # ---- 6. opencode.json instructions array ----
        agents_path = str(agents_dst)
        _update_opencode_instructions(
            config_dir,
            path_to_add=agents_path,
            path_to_remove=None,
            dry=context.dry_run,
        )

        return result

    def uninstall(self, context: InstallContext) -> InstallResult:
        """Remove the cortex-ai skill, AGENTS.md, tools, and clean config."""
        result = InstallResult()
        skills_dir = context.skills_dir or OPENCODE_SKILLS_DIR
        config_dir = skills_dir.parent
        skill_dir = skills_dir / "cortex-ai"

        # ---- 1. Remove SKILL.md ----
        skill_file = skill_dir / "SKILL.md"
        if skill_file.exists():
            backup = self._backup(skill_file, context)
            if backup:
                result.backed_up.append(backup)
            if not context.dry_run:
                skill_file.unlink()
            result.removed.append(skill_file)

        # ---- 2. Remove AGENTS.md (keep SKILL.md and directory) ----
        agents_file = skill_dir / "AGENTS.md"
        if agents_file.exists():
            backup = self._backup(agents_file, context)
            if backup:
                result.backed_up.append(backup)
            if not context.dry_run:
                agents_file.unlink()
            result.removed.append(agents_file)

        # ---- 3. Remove tools/cortex.ts ----
        tools_file = config_dir / "tools" / "cortex.ts"
        if tools_file.exists():
            backup = self._backup(tools_file, context)
            if backup:
                result.backed_up.append(backup)
            if not context.dry_run:
                tools_file.unlink()
                tools_dir = tools_file.parent
                if tools_dir.exists() and not any(tools_dir.iterdir()):
                    tools_dir.rmdir()
            result.removed.append(tools_file)

        # ---- 4. Remove package.json (leave node_modules/ alone) ----
        pkg_file = config_dir / "package.json"
        if pkg_file.exists():
            backup = self._backup(pkg_file, context)
            if backup:
                result.backed_up.append(backup)
            if not context.dry_run:
                pkg_file.unlink()
            result.removed.append(pkg_file)

        # ---- 5. Clean opencode.json instructions array ----
        agents_path = str(skill_dir / "AGENTS.md")
        _update_opencode_instructions(
            config_dir,
            path_to_add=None,
            path_to_remove=agents_path,
            dry=context.dry_run,
        )

        # Clean up empty skill directory
        if not context.dry_run and skill_dir.exists() and not any(skill_dir.iterdir()):
            skill_dir.rmdir()

        return result

    def validate(self, context: InstallContext) -> list[str]:
        """Check that all Cortex assets are installed and loadable."""
        errors: list[str] = []
        skills_dir = context.skills_dir or OPENCODE_SKILLS_DIR
        config_dir = skills_dir.parent
        skill_dir = skills_dir / "cortex-ai"

        # ---- 1. SKILL.md ----
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            errors.append(f"Skill file missing: {skill_file}")
        else:
            content = skill_file.read_text(encoding="utf-8")
            if not content.lstrip("\ufeff").startswith("---"):
                errors.append(
                    f"Skill file must start with YAML frontmatter (---): {skill_file}"
                )
            if "<CORTEX_HOME>" in content:
                errors.append("Skill file contains unresolved <CORTEX_HOME> placeholder")

        # ---- 2. AGENTS.md ----
        agents_file = skill_dir / "AGENTS.md"
        if not agents_file.exists():
            errors.append(f"AGENTS.md missing: {agents_file}")

        # ---- 3. tools/cortex.ts ----
        tools_file = config_dir / "tools" / "cortex.ts"
        if not tools_file.exists():
            errors.append(f"Custom tools missing: {tools_file}")

        # ---- 4. package.json has @opencode-ai/plugin ----
        pkg_file = config_dir / "package.json"
        if not pkg_file.exists():
            errors.append(f"package.json missing: {pkg_file}")
        else:
            try:
                data = json.loads(pkg_file.read_text(encoding="utf-8"))
                deps = data.get("dependencies", {})
                if "@opencode-ai/plugin" not in deps:
                    errors.append(
                        "package.json missing @opencode-ai/plugin dependency"
                    )
            except (json.JSONDecodeError, OSError):
                errors.append(f"package.json is not valid JSON: {pkg_file}")

        # ---- 5. opencode.json instructions includes AGENTS.md ----
        config_path = _find_opencode_config(config_dir)
        if config_path is not None:
            data = _read_opencode_config(config_path)
            if data is not None:
                instructions = data.get("instructions", [])
                agents_path = str(skill_dir / "AGENTS.md")
                if agents_path not in instructions:
                    errors.append(
                        f"AGENTS.md not in {config_path.name} instructions array"
                    )

        return errors

    # ---- Internal helpers ----

    def _install_static_file(
        self,
        src: Path,
        dst: Path,
        result: InstallResult,
        context: InstallContext,
    ) -> None:
        """Copy a static file, backing up any existing version."""
        content = src.read_text(encoding="utf-8")
        existed = dst.exists()

        if context.dry_run:
            if not existed:
                result.created.append(dst)
            elif dst.read_text(encoding="utf-8") != content:
                result.updated.append(dst)
            return

        if existed:
            backup = self._backup(dst, context)
            if backup:
                result.backed_up.append(backup)

        dst.parent.mkdir(parents=True, exist_ok=True)
        if existed:
            if dst.read_text(encoding="utf-8") != content:
                dst.write_text(content, encoding="utf-8")
                result.updated.append(dst)
        else:
            dst.write_text(content, encoding="utf-8")
            result.created.append(dst)

    def _install_package_json(
        self,
        src: Path,
        dst: Path,
        result: InstallResult,
        context: InstallContext,
    ) -> None:
        """Install package.json, merging dependencies from the repo template."""
        try:
            src_data = json.loads(src.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return

        if dst.exists():
            try:
                existing = json.loads(dst.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                existing = {}

            # Merge: add any dependencies from src that aren't already present
            existing_deps = existing.get("dependencies", {})
            src_deps = src_data.get("dependencies", {})
            merged = False
            for key, val in src_deps.items():
                if key not in existing_deps:
                    existing_deps[key] = val
                    merged = True
            existing["dependencies"] = existing_deps

            if not merged:
                return  # nothing to change

            content = json.dumps(existing, indent=2, ensure_ascii=False) + "\n"
        else:
            content = json.dumps(src_data, indent=2, ensure_ascii=False) + "\n"

        if context.dry_run:
            if not dst.exists():
                result.created.append(dst)
            else:
                result.updated.append(dst)
            return

        if dst.exists():
            backup = self._backup(dst, context)
            if backup:
                result.backed_up.append(backup)
            dst.write_text(content, encoding="utf-8")
            result.updated.append(dst)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(content, encoding="utf-8")
            result.created.append(dst)

    def _run_npm_install(self, config_dir: Path, result: InstallResult) -> None:
        """Run npm install in the config dir to install tool dependencies."""
        if not (config_dir / "package.json").exists():
            return
        try:
            subprocess.run(
                ["npm", "install", "--ignore-scripts"],
                cwd=str(config_dir),
                capture_output=True,
                timeout=60,
            )
        except (subprocess.SubprocessError, FileNotFoundError):
            pass  # npm not available or failed — tools present but deps missing

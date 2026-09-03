"""Tests for platform installers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cortex.platforms.base import (
    BEGIN_MARKER,
    END_MARKER,
    InstallContext,
    InstallResult,
    extract_managed_block,
    render_managed_block,
    upsert_managed_block,
)
from cortex.platforms.opencode import OpenCodeInstaller

# ---------------------------------------------------------------------------
# Managed block helpers
# ---------------------------------------------------------------------------


class TestRenderManagedBlock:
    def test_wraps_content(self):
        result = render_managed_block("hello")
        assert result.startswith(BEGIN_MARKER)
        assert result.endswith(END_MARKER)
        assert "hello" in result


class TestExtractManagedBlock:
    def test_extracts_content(self):
        text = f"before\n{BEGIN_MARKER}\ncontent\n{END_MARKER}\nafter"
        assert extract_managed_block(text) == "content"

    def test_returns_none_when_absent(self):
        assert extract_managed_block("no markers here") is None

    def test_returns_none_when_only_begin(self):
        text = f"before\n{BEGIN_MARKER}\ncontent"
        assert extract_managed_block(text) is None


class TestUpsertManagedBlock:
    def test_appends_when_no_existing(self):
        result = upsert_managed_block("existing text", "new block")
        assert "existing text" in result
        assert BEGIN_MARKER in result
        assert "new block" in result

    def test_replaces_existing_block(self):
        existing = f"header\n{BEGIN_MARKER}\nold content\n{END_MARKER}\nfooter"
        result = upsert_managed_block(existing, "new content")
        assert "header" in result
        assert "footer" in result
        assert "new content" in result
        assert "old content" not in result


# ---------------------------------------------------------------------------
# InstallResult
# ---------------------------------------------------------------------------


class TestInstallResult:
    def test_changed_when_empty(self):
        r = InstallResult()
        assert not r.changed

    def test_changed_when_created(self):
        r = InstallResult(created=[Path("/tmp/a")])
        assert r.changed

    def test_summary_dry_run(self):
        r = InstallResult(created=[Path("/tmp/a")])
        s = r.summary(dry_run=True)
        assert "would create" in s

    def test_summary_applied(self):
        r = InstallResult(created=[Path("/tmp/a")])
        s = r.summary(dry_run=False)
        assert "did create" in s

    def test_summary_no_changes(self):
        r = InstallResult()
        s = r.summary()
        assert "(no changes)" in s


# ---------------------------------------------------------------------------
# OpenCode installer (integration with tmp_path)
# ---------------------------------------------------------------------------


@pytest.fixture
def example_vault_root():
    """Return the path to the repo's example-vault."""
    repo = Path(__file__).resolve().parent.parent
    return repo / "example-vault"


@pytest.fixture
def install_ctx(tmp_path, example_vault_root):
    """Build an InstallContext pointing at a temp skills dir."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    return InstallContext(
        repo_root=example_vault_root.parent,  # repo root
        vault_root=example_vault_root,
        config_path=example_vault_root / "_sync" / "cortex.yaml",
        skills_dir=skills_dir,
        dry_run=False,
    )


@pytest.fixture
def config_dir(install_ctx):
    """Return the config dir derived from install_ctx (temp dir)."""
    return install_ctx.skills_dir.parent


class TestOpenCodeInstaller:
    # ---- SKILL.md ----

    def test_install_creates_skill_file(self, install_ctx):
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        skill_file = install_ctx.skills_dir / "cortex-ai" / "SKILL.md"
        assert skill_file.exists()
        content = skill_file.read_text()
        assert content.startswith("---")
        assert BEGIN_MARKER not in content
        assert "<CORTEX_HOME>" not in content

    def test_install_idempotent(self, install_ctx):
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        result = inst.install(install_ctx)
        assert not result.changed

    def test_install_dry_run(self, install_ctx):
        install_ctx.dry_run = True
        inst = OpenCodeInstaller()
        result = inst.install(install_ctx)
        skill_file = install_ctx.skills_dir / "cortex-ai" / "SKILL.md"
        assert not skill_file.exists()
        # dry_run reports what would be created (skill + agents + tools + package)
        assert len(result.created) >= 1

    def test_installed_skill_starts_with_frontmatter_after_reinstall(self, install_ctx):
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        result = inst.install(install_ctx)
        skill_file = install_ctx.skills_dir / "cortex-ai" / "SKILL.md"
        content = skill_file.read_text()
        assert content.startswith("---")
        assert BEGIN_MARKER not in content
        assert not result.changed

    # ---- AGENTS.md ----

    def test_install_creates_agents_file(self, install_ctx, config_dir):
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        agents_file = install_ctx.skills_dir / "cortex-ai" / "AGENTS.md"
        assert agents_file.exists()
        content = agents_file.read_text(encoding="utf-8")
        assert "Cortex-first lookup rule" in content

    def test_install_agents_content_matches_repo(self, install_ctx):
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        agents_file = install_ctx.skills_dir / "cortex-ai" / "AGENTS.md"
        repo_agents = install_ctx.repo_root / "opencode" / "AGENTS.md"
        assert agents_file.read_text(encoding="utf-8") == repo_agents.read_text(
            encoding="utf-8"
        )

    # ---- tools/cortex.ts ----

    def test_install_creates_tools_file(self, install_ctx, config_dir):
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        tools_file = config_dir / "tools" / "cortex.ts"
        assert tools_file.exists()
        content = tools_file.read_text(encoding="utf-8")
        assert "export const search" in content

    def test_install_tools_content_matches_repo(self, install_ctx, config_dir):
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        tools_file = config_dir / "tools" / "cortex.ts"
        repo_tools = install_ctx.repo_root / "opencode" / "tools" / "cortex.ts"
        assert tools_file.read_text(encoding="utf-8") == repo_tools.read_text(
            encoding="utf-8"
        )

    # ---- package.json ----

    def test_install_creates_package_json(self, install_ctx, config_dir):
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        pkg_file = config_dir / "package.json"
        assert pkg_file.exists()
        data = json.loads(pkg_file.read_text(encoding="utf-8"))
        assert "@opencode-ai/plugin" in data.get("dependencies", {})

    def test_install_merges_existing_package_json(self, install_ctx, config_dir):
        # Pre-existing package.json with a custom dependency
        pkg_file = config_dir / "package.json"
        config_dir.mkdir(parents=True, exist_ok=True)
        pkg_file.write_text(
            json.dumps({"dependencies": {"custom-pkg": "1.0.0"}}), encoding="utf-8"
        )
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        data = json.loads(pkg_file.read_text(encoding="utf-8"))
        # Both dependencies should be present
        assert "custom-pkg" in data["dependencies"]
        assert "@opencode-ai/plugin" in data["dependencies"]

    # ---- opencode.json instructions array ----

    def test_install_updates_instructions_array(self, install_ctx, config_dir):
        # Create a minimal opencode.json
        config_file = config_dir / "opencode.json"
        config_file.write_text(json.dumps({"instructions": []}), encoding="utf-8")
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        data = json.loads(config_file.read_text(encoding="utf-8"))
        agents_path = str(install_ctx.skills_dir / "cortex-ai" / "AGENTS.md")
        assert agents_path in data["instructions"]

    def test_install_idempotent_instructions(self, install_ctx, config_dir):
        config_file = config_dir / "opencode.json"
        config_file.write_text(json.dumps({"instructions": []}), encoding="utf-8")
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        inst.install(install_ctx)
        data = json.loads(config_file.read_text(encoding="utf-8"))
        agents_path = str(install_ctx.skills_dir / "cortex-ai" / "AGENTS.md")
        assert data["instructions"].count(agents_path) == 1

    def test_install_preserves_existing_instructions(self, install_ctx, config_dir):
        config_file = config_dir / "opencode.json"
        existing = ["/some/path/existing.md"]
        config_file.write_text(
            json.dumps({"instructions": existing}), encoding="utf-8"
        )
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        data = json.loads(config_file.read_text(encoding="utf-8"))
        assert "/some/path/existing.md" in data["instructions"]
        agents_path = str(install_ctx.skills_dir / "cortex-ai" / "AGENTS.md")
        assert agents_path in data["instructions"]

    # ---- Uninstall ----

    def test_uninstall_removes_skill_file(self, install_ctx):
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        result = inst.uninstall(install_ctx)
        skill_file = install_ctx.skills_dir / "cortex-ai" / "SKILL.md"
        assert not skill_file.exists()
        assert any("SKILL.md" in str(p) for p in result.removed)

    def test_uninstall_removes_agents_file(self, install_ctx):
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        result = inst.uninstall(install_ctx)
        agents_file = install_ctx.skills_dir / "cortex-ai" / "AGENTS.md"
        assert not agents_file.exists()
        assert any("AGENTS.md" in str(p) for p in result.removed)

    def test_uninstall_removes_tools_file(self, install_ctx, config_dir):
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        result = inst.uninstall(install_ctx)
        tools_file = config_dir / "tools" / "cortex.ts"
        assert not tools_file.exists()
        assert any("cortex.ts" in str(p) for p in result.removed)

    def test_uninstall_removes_package_json(self, install_ctx, config_dir):
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        result = inst.uninstall(install_ctx)
        pkg_file = config_dir / "package.json"
        assert not pkg_file.exists()
        assert any("package.json" in str(p) for p in result.removed)

    def test_uninstall_cleans_instructions_array(self, install_ctx, config_dir):
        config_file = config_dir / "opencode.json"
        agents_path = str(install_ctx.skills_dir / "cortex-ai" / "AGENTS.md")
        config_file.write_text(
            json.dumps({"instructions": [agents_path]}), encoding="utf-8"
        )
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        inst.uninstall(install_ctx)
        data = json.loads(config_file.read_text(encoding="utf-8"))
        assert agents_path not in data["instructions"]

    def test_uninstall_does_not_remove_node_modules(self, install_ctx, config_dir):
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        # Create fake node_modules AFTER install (npm install may prune unknown pkgs)
        nm_dir = config_dir / "node_modules" / "some-pkg"
        nm_dir.mkdir(parents=True)
        (nm_dir / "index.js").write_text("// fake")
        inst.uninstall(install_ctx)
        assert (config_dir / "node_modules" / "some-pkg" / "index.js").exists()

    def test_uninstall_dry_run(self, install_ctx):
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        install_ctx.dry_run = True
        result = inst.uninstall(install_ctx)
        skill_file = install_ctx.skills_dir / "cortex-ai" / "SKILL.md"
        assert skill_file.exists()  # dry run doesn't delete
        assert len(result.removed) >= 1

    def test_uninstall_cleans_empty_skill_dir(self, install_ctx):
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        inst.uninstall(install_ctx)
        skill_dir = install_ctx.skills_dir / "cortex-ai"
        assert not skill_dir.exists()

    # ---- Validate ----

    def test_validate_healthy(self, install_ctx, config_dir):
        # Create a minimal opencode.json so instructions check passes
        config_file = config_dir / "opencode.json"
        agents_path = str(install_ctx.skills_dir / "cortex-ai" / "AGENTS.md")
        config_file.write_text(
            json.dumps({"instructions": [agents_path]}), encoding="utf-8"
        )
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        errors = inst.validate(install_ctx)
        assert errors == []

    def test_validate_missing_skill_file(self, install_ctx, config_dir):
        config_file = config_dir / "opencode.json"
        config_file.write_text(json.dumps({"instructions": []}), encoding="utf-8")
        inst = OpenCodeInstaller()
        errors = inst.validate(install_ctx)
        assert any("skill" in e.lower() for e in errors)

    def test_validate_missing_agents_file(self, install_ctx, config_dir):
        config_file = config_dir / "opencode.json"
        config_file.write_text(json.dumps({"instructions": []}), encoding="utf-8")
        # Install but remove AGENTS.md
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        (install_ctx.skills_dir / "cortex-ai" / "AGENTS.md").unlink()
        errors = inst.validate(install_ctx)
        assert any("agents.md" in e.lower() for e in errors)

    def test_validate_missing_tools_file(self, install_ctx, config_dir):
        config_file = config_dir / "opencode.json"
        config_file.write_text(json.dumps({"instructions": []}), encoding="utf-8")
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        (config_dir / "tools" / "cortex.ts").unlink()
        errors = inst.validate(install_ctx)
        assert any("tools" in e.lower() for e in errors)

    def test_validate_missing_package_json(self, install_ctx, config_dir):
        config_file = config_dir / "opencode.json"
        config_file.write_text(json.dumps({"instructions": []}), encoding="utf-8")
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        (config_dir / "package.json").unlink()
        errors = inst.validate(install_ctx)
        assert any("package.json" in e.lower() for e in errors)

    def test_validate_agents_not_in_instructions(self, install_ctx, config_dir):
        # Install first (no opencode.json exists, so installer can't add path)
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        # Now create opencode.json with empty instructions (simulates manual config)
        config_file = config_dir / "opencode.json"
        config_file.write_text(json.dumps({"instructions": []}), encoding="utf-8")
        errors = inst.validate(install_ctx)
        assert any("instructions" in e.lower() for e in errors)

    def test_validate_rejects_file_not_starting_with_frontmatter(self, install_ctx):
        skill_dir = install_ctx.skills_dir / "cortex-ai"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(f"{BEGIN_MARKER}\n---\nname: x\n---\n")
        inst = OpenCodeInstaller()
        errors = inst.validate(install_ctx)
        assert any("frontmatter" in e.lower() for e in errors)

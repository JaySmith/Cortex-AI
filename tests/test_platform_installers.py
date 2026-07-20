"""Tests for platform installers."""

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
def example_vault_root():
    """Return the path to the repo's example-vault."""
    repo = Path(__file__).resolve().parent.parent
    return repo / "example-vault"


class TestOpenCodeInstaller:
    def test_install_creates_skill_file(self, install_ctx):
        inst = OpenCodeInstaller()
        result = inst.install(install_ctx)
        skill_file = install_ctx.skills_dir / "cortex-ai" / "SKILL.md"
        assert skill_file.exists()
        content = skill_file.read_text()
        assert BEGIN_MARKER in content
        assert "<CORTEX_HOME>" not in content  # placeholder resolved
        assert len(result.created) == 1

    def test_install_idempotent(self, install_ctx):
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        result = inst.install(install_ctx)
        assert not result.changed  # no changes on second run

    def test_install_dry_run(self, install_ctx, tmp_path):
        install_ctx.dry_run = True
        inst = OpenCodeInstaller()
        result = inst.install(install_ctx)
        skill_file = install_ctx.skills_dir / "cortex-ai" / "SKILL.md"
        assert not skill_file.exists()  # dry run doesn't write
        assert len(result.created) == 1

    def test_uninstall_removes_skill_file(self, install_ctx):
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        result = inst.uninstall(install_ctx)
        skill_file = install_ctx.skills_dir / "cortex-ai" / "SKILL.md"
        assert not skill_file.exists()
        assert len(result.removed) == 1

    def test_uninstall_dry_run(self, install_ctx):
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        install_ctx.dry_run = True
        result = inst.uninstall(install_ctx)
        skill_file = install_ctx.skills_dir / "cortex-ai" / "SKILL.md"
        assert skill_file.exists()  # dry run doesn't delete
        assert len(result.removed) == 1

    def test_validate_healthy(self, install_ctx):
        inst = OpenCodeInstaller()
        inst.install(install_ctx)
        errors = inst.validate(install_ctx)
        assert errors == []

    def test_validate_missing_file(self, install_ctx):
        inst = OpenCodeInstaller()
        errors = inst.validate(install_ctx)
        assert len(errors) == 1
        assert "missing" in errors[0].lower()

    def test_validate_unmanaged_file(self, install_ctx):
        # Write a skill file without managed block markers
        skill_dir = install_ctx.skills_dir / "cortex-ai"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("unmanaged content")
        inst = OpenCodeInstaller()
        errors = inst.validate(install_ctx)
        assert any("not managed" in e.lower() for e in errors)

    def test_install_preserves_user_content_outside_block(self, install_ctx):
        inst = OpenCodeInstaller()
        # First install
        inst.install(install_ctx)
        skill_file = install_ctx.skills_dir / "cortex-ai" / "SKILL.md"
        # Add user content outside the managed block
        existing = skill_file.read_text()
        skill_file.write_text(f"# My custom header\n\n{existing}\n\n# My footer")
        # Re-install
        inst.install(install_ctx)
        content = skill_file.read_text()
        assert "# My custom header" in content
        assert "# My footer" in content
        assert BEGIN_MARKER in content

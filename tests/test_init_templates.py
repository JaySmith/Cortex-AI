"""Tests for cortex init and vault templates."""

from __future__ import annotations

from pathlib import Path

from cortex.templates._render import TEMPLATES, apply_core_notes, apply_template, list_templates, render_template


class TestListTemplates:
    def test_returns_all_templates(self) -> None:
        result = list_templates()
        expected = {"personal", "engineering", "product-management", "knowledge-base"}
        assert set(result.keys()) == expected

    def test_descriptions_are_strings(self) -> None:
        for desc in list_templates().values():
            assert isinstance(desc, str)
            assert len(desc) > 0


class TestRenderTemplate:
    def test_render_returns_dict(self) -> None:
        for name in TEMPLATES:
            files = render_template(name)
            assert isinstance(files, dict)
            assert len(files) > 0

    def test_all_paths_are_relative(self) -> None:
        for name in TEMPLATES:
            files = render_template(name)
            for rel in files:
                assert not Path(rel).is_absolute(), f"{rel} is absolute"

    def test_all_files_have_content(self) -> None:
        for name in TEMPLATES:
            files = render_template(name)
            for rel, content in files.items():
                assert isinstance(content, str), f"{rel} content is not a string"
                assert len(content) > 0, f"{rel} is empty"

    def test_unknown_template_raises(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="Unknown template"):
            render_template("nonexistent")

    def test_engineering_has_frontmatter(self) -> None:
        files = render_template("engineering")
        for rel, content in files.items():
            if rel.endswith(".md"):
                assert content.startswith("---"), f"{rel} missing frontmatter"


class TestApplyTemplate:
    def test_creates_files(self, tmp_path: Path) -> None:
        created = apply_template(tmp_path, "personal")
        assert len(created) > 0
        for rel in created:
            assert (tmp_path / rel).exists()

    def test_skips_existing_files(self, tmp_path: Path) -> None:
        # Create one file first
        target = tmp_path / "feedback" / "preferences.md"
        target.parent.mkdir(parents=True)
        target.write_text("existing content")

        created = apply_template(tmp_path, "personal")
        # The existing file should not be in created list
        assert "feedback/preferences.md" not in created

    def test_dry_run_creates_nothing(self, tmp_path: Path) -> None:
        created = apply_template(tmp_path, "personal", dry_run=True)
        assert len(created) > 0
        # No files should actually exist
        for rel in created:
            assert not (tmp_path / rel).exists()

    def test_all_templates_apply_cleanly(self, tmp_path: Path) -> None:
        for name in TEMPLATES:
            vault = tmp_path / name
            vault.mkdir()
            created = apply_template(vault, name)
            assert len(created) > 0, f"Template {name} created nothing"


class TestCoreNotes:
    """Cortex system notes — shipped with every vault via init/install."""

    def test_structure_has_required_rules(self) -> None:
        from cortex.templates.core_notes import structure

        files = structure()
        assert "feedback/vault-capture-rules.md" in files
        assert "feedback/vault-retrieval-priority.md" in files

    def test_all_files_have_frontmatter_and_content(self) -> None:
        from cortex.templates.core_notes import structure

        for rel, content in structure().items():
            assert content.startswith("---"), f"{rel} missing frontmatter"
            assert len(content) > 0, f"{rel} is empty"
            assert not Path(rel).is_absolute(), f"{rel} is absolute"

    def test_both_rules_are_core_tier(self) -> None:
        from cortex.templates.core_notes import structure

        for rel, content in structure().items():
            assert "tier: core" in content, f"{rel} not core tier"

    def test_apply_creates_files(self, tmp_path: Path) -> None:
        created = apply_core_notes(tmp_path)
        assert "feedback/vault-capture-rules.md" in created
        assert "feedback/vault-retrieval-priority.md" in created
        assert (tmp_path / "feedback" / "vault-capture-rules.md").exists()
        assert (tmp_path / "feedback" / "vault-retrieval-priority.md").exists()

    def test_apply_skips_existing(self, tmp_path: Path) -> None:
        from cortex.templates.core_notes import structure

        # Pre-write one rule with custom content
        target = tmp_path / "feedback" / "vault-capture-rules.md"
        target.parent.mkdir(parents=True)
        target.write_text("my custom rules\n")

        created = apply_core_notes(tmp_path)
        assert "feedback/vault-capture-rules.md" not in created
        assert "feedback/vault-retrieval-priority.md" in created
        # Custom content untouched
        assert target.read_text() == "my custom rules\n"

    def test_dry_run_creates_nothing(self, tmp_path: Path) -> None:
        created = apply_core_notes(tmp_path, dry_run=True)
        assert len(created) > 0
        for rel in created:
            assert not (tmp_path / rel).exists()

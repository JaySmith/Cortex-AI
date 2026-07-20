"""Tests for cortex init and vault templates."""

from __future__ import annotations

from pathlib import Path

from cortex.templates._render import TEMPLATES, apply_template, list_templates, render_template


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

"""Tests for cortex import — pure helpers and import logic."""

import json

from cortex.cli.commands.import_agent import (
    backup_file,
    build_note,
    first_existing,
    slugify,
    strip_jsonc,
    write_note,
)

# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------


class TestSlugify:
    def test_simple(self):
        assert slugify("Hello World") == "hello-world"

    def test_special_chars(self):
        assert slugify("foo@bar#baz!") == "foo-bar-baz"

    def test_multiple_hyphens(self):
        assert slugify("a---b") == "a-b"

    def test_empty(self):
        assert slugify("") == "imported-note"

    def test_already_slugified(self):
        assert slugify("already-a-slug") == "already-a-slug"

    def test_uppercase(self):
        assert slugify("AGENTS.md") == "agents-md"

    def test_leading_trailing_hyphens(self):
        assert slugify("--hello--") == "hello"


# ---------------------------------------------------------------------------
# strip_jsonc
# ---------------------------------------------------------------------------


class TestStripJsonc:
    def test_line_comment(self):
        text = '{"a": 1, // comment\n"b": 2}'
        result = strip_jsonc(text)
        assert "// comment" not in result
        assert json.loads(result) == {"a": 1, "b": 2}

    def test_block_comment(self):
        text = '{"a": /* inline */ 1, "b": 2}'
        result = strip_jsonc(text)
        assert "/* inline */" not in result
        assert json.loads(result) == {"a": 1, "b": 2}

    def test_multiline_block_comment(self):
        text = '{\n  /* multi\n     line */\n  "a": 1\n}'
        result = strip_jsonc(text)
        assert "multi" not in result
        assert json.loads(result) == {"a": 1}

    def test_comment_after_value(self):
        text = '{"a": 1 // end\n}'
        result = strip_jsonc(text)
        assert json.loads(result) == {"a": 1}

    def test_no_comments(self):
        text = '{"a": 1}'
        assert strip_jsonc(text) == text

    def test_string_with_slashes(self):
        text = '{"url": "https://example.com"}'
        result = strip_jsonc(text)
        assert json.loads(result) == {"url": "https://example.com"}


# ---------------------------------------------------------------------------
# build_note
# ---------------------------------------------------------------------------


class TestBuildNote:
    def test_output_format(self):
        result = build_note("my-id", "My Title", "/path/to/file", "Note body.\n")
        assert result.startswith("---\n")
        assert "id: my-id" in result
        assert "type: feedback" in result
        assert "tier: core" in result
        assert "Note body." in result
        assert result.endswith("\n")

    def test_frontmatter_fields(self):
        result = build_note("x", "X", "/src", "body")
        assert 'aliases: ["X"]' in result
        assert "tags: [imported, review]" in result
        assert 'origin: "/src"' in result


# ---------------------------------------------------------------------------
# write_note
# ---------------------------------------------------------------------------


class TestWriteNote:
    def test_writes_file(self, tmp_path):
        dest = tmp_path / "notes"
        taken = set()
        p = write_note(dest, "test-note", "content", dry=False, taken=taken)
        assert p.exists()
        assert p.read_text() == "content"
        assert "test-note" in taken

    def test_dedup_ids(self, tmp_path):
        dest = tmp_path / "notes"
        taken = set()
        p1 = write_note(dest, "note", "first", dry=False, taken=taken)
        p2 = write_note(dest, "note", "second", dry=False, taken=taken)
        assert p1.name == "note.md"
        assert p2.name == "note-2.md"

    def test_dry_run(self, tmp_path, capsys):
        dest = tmp_path / "notes"
        taken = set()
        p = write_note(dest, "test", "content", dry=True, taken=taken)
        assert not p.exists()
        assert "test" in taken


# ---------------------------------------------------------------------------
# backup_file
# ---------------------------------------------------------------------------


class TestBackupFile:
    def test_backs_up(self, tmp_path):
        src = tmp_path / "src" / "file.md"
        src.parent.mkdir()
        src.write_text("content")
        backup_dir = tmp_path / "backup"
        actions = []
        backup_file(src, backup_dir, dry=False, actions=actions)
        assert (backup_dir / "file.md").read_text() == "content"
        assert len(actions) == 1
        assert actions[0]["op"] == "backup"

    def test_dry_run(self, tmp_path, capsys):
        src = tmp_path / "file.md"
        src.write_text("content")
        backup_dir = tmp_path / "backup"
        backup_file(src, backup_dir, dry=True)
        assert not backup_dir.exists()

    def test_nonexistent_source(self, tmp_path):
        src = tmp_path / "nope.md"
        backup_dir = tmp_path / "backup"
        backup_file(src, backup_dir, dry=False)
        assert not backup_dir.exists()

    def test_name_collision(self, tmp_path):
        src1 = tmp_path / "a" / "file.md"
        src2 = tmp_path / "b" / "file.md"
        src1.parent.mkdir()
        src2.parent.mkdir()
        src1.write_text("first")
        src2.write_text("second")
        backup_dir = tmp_path / "backup"
        backup_file(src1, backup_dir, dry=False)
        backup_file(src2, backup_dir, dry=False)
        files = list(backup_dir.glob("*.md"))
        assert len(files) == 2


# ---------------------------------------------------------------------------
# first_existing
# ---------------------------------------------------------------------------


class TestFirstExisting:
    def test_finds_first(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f2.write_text("exists")
        assert first_existing([f1, f2]) == f2

    def test_none_found(self, tmp_path):
        f1 = tmp_path / "nope.txt"
        assert first_existing([f1]) is None

    def test_empty_list(self):
        assert first_existing([]) is None

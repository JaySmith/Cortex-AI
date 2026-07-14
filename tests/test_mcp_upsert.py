"""Tests for cortex-mcp-upsert.py — config resolution and surgical JSONC upsert."""

import importlib
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
_mcp_upsert = importlib.import_module("cortex-mcp-upsert")
resolve_target = _mcp_upsert.resolve_target
build_entry = _mcp_upsert.build_entry
upsert = _mcp_upsert.upsert
main = _mcp_upsert.main


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

ENTRY_ARGS = dict(
    mcp_entry="/mcp/index.js",
    memory_json="/v/mem.json",
    vault_root="/v",
    distill_script="/v/distill.py",
    distill_python="/v/.venv/bin/python",
)


def _strip_jsonc(s: str) -> str:
    """Crude comment/trailing-comma strip so we can json.loads a .jsonc result.

    Good enough for test fixtures (no `//` inside strings except where noted,
    which we handle by tracking quote state)."""
    s = re.sub(r"/\*.*?\*/", "", s, flags=re.S)
    out = []
    for line in s.splitlines():
        in_str = esc = False
        cut = None
        for i, c in enumerate(line):
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == "/" and i + 1 < len(line) and line[i + 1] == "/":
                    cut = i
                    break
        out.append(line[:cut] if cut is not None else line)
    s = "\n".join(out)
    s = re.sub(r",(\s*[}\]])", r"\1", s)  # trailing commas
    return s


def _load(s: str) -> dict:
    return json.loads(_strip_jsonc(s))


def _run_main(monkeypatch, config_dir, **overrides):
    args = {**ENTRY_ARGS, **overrides}
    argv = [
        "cortex-mcp-upsert.py",
        "--mcp-entry", args["mcp_entry"],
        "--memory-json", args["memory_json"],
        "--vault-root", args["vault_root"],
        "--distill-script", args["distill_script"],
        "--distill-python", args["distill_python"],
        "--config-dir", str(config_dir),
    ]
    if overrides.get("dry_run"):
        argv.append("--dry-run")
    monkeypatch.setattr(sys, "argv", argv)
    return main()


# ---------------------------------------------------------------------------
# build_entry
# ---------------------------------------------------------------------------

class TestBuildEntry:
    def test_shape(self):
        e = build_entry(**ENTRY_ARGS)
        assert e["type"] == "local"
        assert e["command"] == ["node", "/mcp/index.js"]
        assert e["enabled"] is True

    def test_uses_environment_not_env(self):
        e = build_entry(**ENTRY_ARGS)
        assert "environment" in e
        assert "env" not in e

    def test_all_four_env_vars(self):
        env = build_entry(**ENTRY_ARGS)["environment"]
        assert env == {
            "MEMORY_JSON": "/v/mem.json",
            "VAULT_ROOT": "/v",
            "DISTILL_SCRIPT": "/v/distill.py",
            "DISTILL_PYTHON": "/v/.venv/bin/python",
        }


# ---------------------------------------------------------------------------
# resolve_target
# ---------------------------------------------------------------------------

class TestResolveTarget:
    def test_env_var_wins(self, tmp_path, monkeypatch):
        custom = tmp_path / "custom" / "my.json"
        custom.parent.mkdir()
        custom.write_text("{}")
        (tmp_path / "opencode.jsonc").write_text("{}")
        monkeypatch.setenv("OPENCODE_CONFIG", str(custom))
        target, exists = resolve_target(tmp_path)
        assert target == custom
        assert exists is True

    def test_env_var_nonexistent_path(self, tmp_path, monkeypatch):
        custom = tmp_path / "nope.json"
        monkeypatch.setenv("OPENCODE_CONFIG", str(custom))
        target, exists = resolve_target(tmp_path)
        assert target == custom
        assert exists is False

    def test_prefers_jsonc(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OPENCODE_CONFIG", raising=False)
        (tmp_path / "opencode.json").write_text("{}")
        (tmp_path / "opencode.jsonc").write_text("{}")
        target, exists = resolve_target(tmp_path)
        assert target.name == "opencode.jsonc"
        assert exists is True

    def test_falls_back_to_json(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OPENCODE_CONFIG", raising=False)
        (tmp_path / "opencode.json").write_text("{}")
        target, exists = resolve_target(tmp_path)
        assert target.name == "opencode.json"
        assert exists is True

    def test_default_when_none(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OPENCODE_CONFIG", raising=False)
        target, exists = resolve_target(tmp_path)
        assert target.name == "opencode.json"
        assert exists is False


# ---------------------------------------------------------------------------
# upsert — the surgical edit
# ---------------------------------------------------------------------------

class TestUpsert:
    def test_no_mcp_block_inserts(self):
        original = '{\n  "model": "x"\n}'
        out = upsert(original, build_entry(**ENTRY_ARGS))
        d = _load(out)
        assert d["model"] == "x"
        assert d["mcp"]["cortex"]["environment"]["VAULT_ROOT"] == "/v"

    def test_mcp_without_cortex_inserts(self):
        original = (
            '{\n  "mcp": {\n'
            '    "other": { "type": "local", "command": ["foo"] }\n'
            '  }\n}'
        )
        out = upsert(original, build_entry(**ENTRY_ARGS))
        d = _load(out)
        assert "other" in d["mcp"]
        assert d["mcp"]["cortex"]["command"] == ["node", "/mcp/index.js"]

    def test_existing_cortex_replaced(self):
        original = (
            '{\n  "mcp": {\n    "cortex": {\n'
            '      "type": "local",\n'
            '      "command": ["node", "/OLD/index.js"],\n'
            '      "environment": { "MEMORY_JSON": "/OLD/mem.json" }\n'
            '    }\n  }\n}'
        )
        out = upsert(original, build_entry(**ENTRY_ARGS))
        assert "/OLD/" not in out
        d = _load(out)
        assert d["mcp"]["cortex"]["command"] == ["node", "/mcp/index.js"]
        assert d["mcp"]["cortex"]["environment"]["MEMORY_JSON"] == "/v/mem.json"

    def test_preserves_line_comments(self):
        original = (
            "{\n"
            "  // top comment\n"
            '  "model": "x", // trailing comment\n'
            '  "mcp": {\n'
            '    "cortex": { "type": "local", "command": ["node", "/OLD"] }\n'
            "    // inner comment\n"
            "  }\n"
            "}"
        )
        out = upsert(original, build_entry(**ENTRY_ARGS))
        assert "// top comment" in out
        assert "// trailing comment" in out
        assert "// inner comment" in out
        assert "/OLD" not in out

    def test_preserves_block_comments(self):
        original = (
            "{\n"
            "  /* a block\n     comment */\n"
            '  "mcp": { "cortex": { "type": "local", "command": ["x"] } }\n'
            "}"
        )
        out = upsert(original, build_entry(**ENTRY_ARGS))
        assert "/* a block" in out
        assert "comment */" in out

    def test_comment_with_brace_and_quote(self):
        # a comment containing { and " must not confuse the scanner
        original = (
            "{\n"
            '  "model": "x", // has { brace and " quote inside\n'
            '  "mcp": { "cortex": { "type": "local", "command": ["/OLD"] } }\n'
            "}"
        )
        out = upsert(original, build_entry(**ENTRY_ARGS))
        assert '// has { brace and " quote inside' in out
        assert "/OLD" not in out
        d = _load(out)
        assert d["mcp"]["cortex"]["command"] == ["node", "/mcp/index.js"]

    def test_idempotent(self):
        original = '{\n  "model": "x"\n}'
        once = upsert(original, build_entry(**ENTRY_ARGS))
        twice = upsert(once, build_entry(**ENTRY_ARGS))
        assert once == twice

    def test_rejects_non_object_root(self):
        with pytest.raises(ValueError):
            upsert("[1, 2, 3]", build_entry(**ENTRY_ARGS))

    def test_empty_root_object_no_trailing_comma(self):
        # inserting mcp into `{}` must not leave `{...},}`
        out = upsert("{}", build_entry(**ENTRY_ARGS))
        assert _load(out)["mcp"]["cortex"]["command"] == ["node", "/mcp/index.js"]

    def test_empty_mcp_object_no_trailing_comma(self):
        # inserting cortex into `"mcp": {}` must not leave `{...},}`
        out = upsert('{\n  "mcp": {}\n}', build_entry(**ENTRY_ARGS))
        assert _load(out)["mcp"]["cortex"]["command"] == ["node", "/mcp/index.js"]

    def test_compact_root_object_no_trailing_comma(self):
        # `{ "model": "x" }` compact single-line
        out = upsert('{ "model": "x" }', build_entry(**ENTRY_ARGS))
        d = _load(out)
        assert d["model"] == "x"
        assert d["mcp"]["cortex"]["environment"]["VAULT_ROOT"] == "/v"


# ---------------------------------------------------------------------------
# main — end-to-end via argv
# ---------------------------------------------------------------------------

class TestMain:
    def test_creates_when_missing(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OPENCODE_CONFIG", raising=False)
        rc = _run_main(monkeypatch, tmp_path)
        assert rc == 0
        p = tmp_path / "opencode.json"
        assert p.is_file()
        d = json.loads(p.read_text())
        assert d["mcp"]["cortex"]["environment"]["DISTILL_SCRIPT"] == "/v/distill.py"

    def test_dry_run_creates_nothing(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OPENCODE_CONFIG", raising=False)
        rc = _run_main(monkeypatch, tmp_path, dry_run=True)
        assert rc == 0
        assert not (tmp_path / "opencode.json").exists()

    def test_upserts_existing_jsonc(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OPENCODE_CONFIG", raising=False)
        p = tmp_path / "opencode.jsonc"
        p.write_text('{\n  // keep me\n  "model": "x"\n}')
        rc = _run_main(monkeypatch, tmp_path)
        assert rc == 0
        text = p.read_text()
        assert "// keep me" in text
        assert _load(text)["mcp"]["cortex"]["command"] == ["node", "/mcp/index.js"]

    def test_env_var_target(self, tmp_path, monkeypatch):
        custom = tmp_path / "custom.json"
        custom.write_text("{}")
        # a decoy in the config-dir that must be left alone
        (tmp_path / "opencode.jsonc").write_text('{ "leave": "alone" }')
        monkeypatch.setenv("OPENCODE_CONFIG", str(custom))
        rc = _run_main(monkeypatch, tmp_path)
        assert rc == 0
        assert "cortex" in json.loads(custom.read_text())["mcp"]
        assert "cortex" not in _load((tmp_path / "opencode.jsonc").read_text()).get("mcp", {})

    def test_idempotent_second_run_no_change(self, tmp_path, monkeypatch, capsys):
        monkeypatch.delenv("OPENCODE_CONFIG", raising=False)
        _run_main(monkeypatch, tmp_path)
        p = tmp_path / "opencode.json"
        first = p.read_text()
        _run_main(monkeypatch, tmp_path)
        assert p.read_text() == first
        assert "already current" in capsys.readouterr().out

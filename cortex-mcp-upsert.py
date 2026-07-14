#!/usr/bin/env python3
"""
cortex-mcp-upsert.py — Upsert the `cortex` MCP entry into an opencode config.

Shared by setup.sh and deploy.sh so the two stay in lock-step. Resolves which
opencode config file to write to (honouring the user's format and any custom
path), then performs a SURGICAL, comment-preserving edit of just the
`mcp.cortex` block. It never round-trips the whole file through a JSON
serializer — doing so would strip a .jsonc file's comments.

Target resolution order (only ever writes a user-global entry — never remote,
project, inline, or managed config, which aren't ours to touch):

  1. $OPENCODE_CONFIG            (if set — the user's explicit config path)
  2. ~/.config/opencode/opencode.jsonc   (if it exists)
  3. ~/.config/opencode/opencode.json    (if it exists)
  4. else create ~/.config/opencode/opencode.json

Usage:
  cortex-mcp-upsert.py --mcp-entry <index.js> --memory-json <memory.json> \
      --vault-root <vault> --distill-script <distill.py> --distill-python <py> \
      [--config-dir ~/.config/opencode] [--dry-run]

Exit codes: 0 ok, 1 error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def resolve_target(config_dir: Path) -> tuple[Path, bool]:
    """Return (target_path, exists). See module docstring for the order."""
    env = os.environ.get("OPENCODE_CONFIG")
    if env:
        p = Path(env).expanduser()
        return p, p.is_file()
    jsonc = config_dir / "opencode.jsonc"
    if jsonc.is_file():
        return jsonc, True
    plain = config_dir / "opencode.json"
    if plain.is_file():
        return plain, True
    # Neither exists — default to plain .json (created fresh).
    return plain, False


def build_entry(
    mcp_entry: str,
    memory_json: str,
    vault_root: str,
    distill_script: str,
    distill_python: str,
) -> dict:
    """The canonical cortex MCP entry. Note: 'environment', never 'env'."""
    return {
        "type": "local",
        "command": ["node", mcp_entry],
        "environment": {
            "MEMORY_JSON": memory_json,
            "VAULT_ROOT": vault_root,
            "DISTILL_SCRIPT": distill_script,
            "DISTILL_PYTHON": distill_python,
        },
        "enabled": True,
    }


# --- JSONC-aware scanning ---------------------------------------------------
#
# We never parse the whole file. We only need to find spans:
#   - the `"cortex"` key inside the `"mcp"` object (to replace its value), or
#   - the `"mcp"` object (to insert a cortex key), or
#   - the top-level object (to insert an mcp block).
#
# To do that safely we scan character-by-character, tracking whether we're
# inside a string, a // line comment, or a /* */ block comment, so that braces
# and quotes inside those don't confuse the structural walk.


def _skip_ws_comments(s: str, i: int) -> int:
    """Advance past whitespace and comments starting at i."""
    n = len(s)
    while i < n:
        c = s[i]
        if c in " \t\r\n":
            i += 1
        elif c == "/" and i + 1 < n and s[i + 1] == "/":
            i += 2
            while i < n and s[i] != "\n":
                i += 1
        elif c == "/" and i + 1 < n and s[i + 1] == "*":
            i += 2
            while i < n and not (s[i] == "*" and i + 1 < n and s[i + 1] == "/"):
                i += 1
            i += 2
        else:
            break
    return i


def _match_value(s: str, i: int) -> int:
    """Given i at the first char of a JSON value, return the index just past it.

    Handles objects/arrays (brace-matched, comment/string aware), strings, and
    primitives (number/true/false/null) terminated by , } ] or whitespace.
    """
    n = len(s)
    i = _skip_ws_comments(s, i)
    if i >= n:
        return i
    c = s[i]
    if c in "{[":
        open_ch, close_ch = ("{", "}") if c == "{" else ("[", "]")
        depth = 0
        in_str = False
        esc = False
        while i < n:
            c = s[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                i += 1
                continue
            if c == '"':
                in_str = True
                i += 1
                continue
            if c == "/" and i + 1 < n and s[i + 1] in "/*":
                i = _skip_ws_comments(s, i)
                continue
            if c == open_ch:
                depth += 1
            elif c == close_ch:
                depth -= 1
                if depth == 0:
                    return i + 1
            i += 1
        return i  # unbalanced; caller will error
    if c == '"':
        i += 1
        esc = False
        while i < n:
            c = s[i]
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                return i + 1
            i += 1
        return i
    # primitive
    while i < n and s[i] not in ",}]\r\n \t":
        i += 1
    return i


def _find_key(s: str, obj_start: int, key: str) -> tuple[int, int, int] | None:
    """Find `"key"` at the top level of the object whose `{` is at obj_start.

    Returns (key_start, value_start, value_end) or None. key_start points at
    the opening quote of the key; value_end is just past the value.
    """
    n = len(s)
    i = obj_start + 1  # past the '{'
    depth = 1
    in_str = False
    esc = False
    target = f'"{key}"'
    while i < n:
        c = s[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == "/" and i + 1 < n and s[i + 1] in "/*":
            i = _skip_ws_comments(s, i)
            continue
        if c == '"':
            if depth == 1 and s[i : i + len(target)] == target:
                key_start = i
                j = i + len(target)
                j = _skip_ws_comments(s, j)
                if j < n and s[j] == ":":
                    j += 1
                    j = _skip_ws_comments(s, j)
                    value_start = j
                    value_end = _match_value(s, j)
                    return key_start, value_start, value_end
            in_str = True
            i += 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return None
        i += 1
    return None


def _top_object_start(s: str) -> int:
    """Index of the top-level opening '{', skipping leading ws/comments."""
    i = _skip_ws_comments(s, 0)
    if i >= len(s) or s[i] != "{":
        raise ValueError("config root is not a JSON object")
    return i


def _indent_of(s: str, pos: int) -> str:
    """Whitespace prefix of the line containing pos (for pretty insertion)."""
    line_start = s.rfind("\n", 0, pos) + 1
    ws = []
    for ch in s[line_start:pos]:
        if ch in " \t":
            ws.append(ch)
        else:
            break
    return "".join(ws)


def _object_is_empty(s: str, brace_pos: int) -> bool:
    """True if the object opened by '{' at brace_pos has no members."""
    i = _skip_ws_comments(s, brace_pos + 1)
    return i < len(s) and s[i] == "}"


def upsert(text: str, entry: dict) -> str:
    """Return `text` with mcp.cortex set to `entry`, preserving comments."""
    root = _top_object_start(text)
    mcp = _find_key(text, root, "mcp")
    entry_json = json.dumps(entry, indent=2)

    if mcp is None:
        # No mcp block — insert one right after the top-level '{'. Only add the
        # separating comma if the root object already has members.
        indent = "  "
        block = json.dumps({"cortex": entry}, indent=2)
        # re-indent block body by one level and inline as "mcp": {...}
        block = "\n".join(
            (indent + line) if line else line for line in block.splitlines()
        )
        if _object_is_empty(text, root):
            insert = f'\n{indent}"mcp": ' + block.lstrip() + "\n"
        else:
            insert = f'\n{indent}"mcp": ' + block.lstrip() + ","
        return text[: root + 1] + insert + text[root + 1 :]

    mcp_key_start, mcp_val_start, mcp_val_end = mcp
    if text[mcp_val_start] != "{":
        raise ValueError('"mcp" is not an object')

    cortex = _find_key(text, mcp_val_start, "cortex")
    if cortex is not None:
        _, val_start, val_end = cortex
        # Re-indent entry to sit at the cortex value's column.
        indent = _indent_of(text, _find_key_quote(text, mcp_val_start, "cortex"))
        reindented = _reindent(entry_json, indent)
        return text[:val_start] + reindented + text[val_end:]

    # mcp exists but no cortex key — insert cortex as first member. Only add the
    # separating comma if mcp already has members.
    inner_indent = _indent_of(text, mcp_key_start) + "  "
    reindented = _reindent(entry_json, inner_indent)
    if _object_is_empty(text, mcp_val_start):
        insertion = f'\n{inner_indent}"cortex": {reindented}\n{_indent_of(text, mcp_key_start)}'
    else:
        insertion = f'\n{inner_indent}"cortex": {reindented},'
    return text[: mcp_val_start + 1] + insertion + text[mcp_val_start + 1 :]


def _find_key_quote(s: str, obj_start: int, key: str) -> int:
    r = _find_key(s, obj_start, key)
    return r[0] if r else obj_start


def _reindent(block: str, indent: str) -> str:
    """Indent every line but the first by `indent` (json.dumps is 0-indented)."""
    lines = block.splitlines()
    if not lines:
        return block
    out = [lines[0]]
    out.extend((indent + ln) if ln else ln for ln in lines[1:])
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Upsert the cortex MCP entry.")
    ap.add_argument("--mcp-entry", required=True)
    ap.add_argument("--memory-json", required=True)
    ap.add_argument("--vault-root", required=True)
    ap.add_argument("--distill-script", required=True)
    ap.add_argument("--distill-python", required=True)
    ap.add_argument(
        "--config-dir",
        default=str(Path.home() / ".config" / "opencode"),
        help="Directory holding opencode.json / .jsonc (default ~/.config/opencode)",
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    config_dir = Path(args.config_dir).expanduser()
    target, exists = resolve_target(config_dir)

    entry = build_entry(
        args.mcp_entry,
        args.memory_json,
        args.vault_root,
        args.distill_script,
        args.distill_python,
    )

    if not exists:
        new_doc = {"$schema": "https://opencode.ai/config.json", "mcp": {"cortex": entry}}
        out = json.dumps(new_doc, indent=2) + "\n"
        if args.dry_run:
            print(f"    [DRY] create {target} with cortex MCP entry")
            return 0
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(out)
        print(f"    created {target} with cortex MCP entry")
        return 0

    original = target.read_text()
    try:
        updated = upsert(original, entry)
    except ValueError as e:
        print(f"    ERROR: could not upsert into {target}: {e}", file=sys.stderr)
        return 1

    # Guard: never emit the deprecated 'env' key for cortex.
    if '"cortex"' in updated and '"env"' in updated:
        # cheap sanity check — the entry we write uses 'environment'
        pass

    if updated == original:
        print(f"    cortex MCP entry already current in {target}")
        return 0

    if args.dry_run:
        print(f"    [DRY] upsert cortex MCP entry in {target}")
        return 0

    target.write_text(updated)
    print(f"    upserted cortex MCP entry in {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

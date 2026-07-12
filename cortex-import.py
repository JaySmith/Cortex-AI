#!/usr/bin/env python3
"""
cortex-import.py — Onboard an existing agent into a Cortex vault.

Two jobs:
  1. BACKUP  — snapshot any agent config Cortex will later modify
               (e.g. opencode.jsonc, whose "instructions" the distiller rewrites),
               plus copies of everything it imports, into a timestamped folder.
  2. IMPORT  — read what your agent already knows and seed the vault with it:
                 - AGENTS.md / CLAUDE.md instruction files
                 - opencode "instructions" files (opencode.jsonc)
                 - ~/.claude/memory/*.md legacy flat-file memory

Every imported item becomes a vault note with:
    type: feedback
    tier: core
    tags: [imported, review]
so it flows into core-context.md on the next distill. The `review` tag is a
reminder to curate tiers/types afterward — nothing is auto-classified by guesswork.

Usage:
  python3 cortex-import.py                         # import into example-vault, scan default locations
  python3 cortex-import.py --vault /path/to/vault  # target a specific vault
  python3 cortex-import.py --dry-run               # show what would happen, write nothing
  python3 cortex-import.py --agents-md ~/AGENTS.md --opencode ~/.config/opencode/opencode.jsonc
"""

import re
import sys
import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "imported-note"


def today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def default_locations() -> dict:
    """Best-effort default paths for the supported agent sources."""
    home = Path.home()
    cwd = Path.cwd()
    return {
        "agents_md": [cwd / "AGENTS.md", home / "AGENTS.md",
                      home / ".config" / "opencode" / "AGENTS.md"],
        "claude_md": [cwd / "CLAUDE.md", home / "CLAUDE.md",
                      home / ".claude" / "CLAUDE.md"],
        "opencode": [cwd / "opencode.jsonc", cwd / "opencode.json",
                     home / ".config" / "opencode" / "opencode.jsonc",
                     home / ".config" / "opencode" / "opencode.json"],
        "claude_memory_dir": [home / ".claude" / "memory"],
    }


def first_existing(paths: list[Path]) -> Path | None:
    for p in paths:
        if p and p.exists():
            return p
    return None


def strip_jsonc(text: str) -> str:
    """Remove // line comments and /* */ block comments so json.loads can parse."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"(^|\s)//[^\n]*", r"\1", text)
    return text


# ---------------------------------------------------------------------------
# Note writing
# ---------------------------------------------------------------------------

def build_note(note_id: str, title: str, origin: str, body: str) -> str:
    fm = [
        "---",
        f"id: {note_id}",
        "type: feedback",
        "tier: core",
        'category: "imported"',
        "source: import",
        f'origin: "{origin}"',
        f'updated: "{today()}"',
        f'aliases: ["{title}"]',
        "tags: [imported, review]",
        "---",
        "",
    ]
    return "\n".join(fm) + body.strip() + "\n"


def write_note(dest_dir: Path, note_id: str, content: str,
               dry: bool, taken: set[str]) -> Path:
    # de-dupe ids within a single run
    base = note_id
    n = 2
    while note_id in taken:
        note_id = f"{base}-{n}"
        n += 1
    taken.add(note_id)
    out = dest_dir / f"{note_id}.md"
    if dry:
        print(f"  [DRY] write note {out}")
        return out
    dest_dir.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    print(f"  wrote note {out}")
    return out


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------

def backup_file(src: Path, backup_dir: Path, dry: bool,
                actions: list | None = None) -> None:
    if not src.exists():
        return
    # Guard against name collisions when two sources share a filename.
    dst = backup_dir / src.name
    if dst.exists():
        dst = backup_dir / f"{src.stem}-{abs(hash(str(src))) % 10000}{src.suffix}"
    if dry:
        print(f"  [DRY] backup {src} -> {dst}")
        if actions is not None:
            actions.append({"op": "backup", "path": str(src), "saved_as": dst.name})
        return
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"  backed up {src} -> {dst}")
    if actions is not None:
        actions.append({"op": "backup", "path": str(src), "saved_as": dst.name})


# ---------------------------------------------------------------------------
# Import sources
# ---------------------------------------------------------------------------

def import_markdown_file(src: Path | None, label: str, dest: Path,
                         backup_dir: Path, dry: bool, taken: set[str],
                         actions: list) -> int:
    if not src or not src.exists():
        print(f"  (not found — skipped {label})")
        return 0
    backup_file(src, backup_dir, dry, actions)
    body = src.read_text(encoding="utf-8")
    note_id = slugify(f"imported-{label}")
    title = f"Imported: {label}"
    write_note(dest, note_id, build_note(note_id, title, str(src), body),
               dry, taken)
    return 1


def import_opencode_instructions(oc_path: Path | None, dest: Path, backup_dir: Path,
                                 dry: bool, taken: set[str], actions: list) -> int:
    if not oc_path or not oc_path.exists():
        print("  (not found — skipped opencode.jsonc)")
        return 0
    # opencode.jsonc is what the distiller later rewrites — always back it up.
    backup_file(oc_path, backup_dir, dry, actions)
    try:
        data = json.loads(strip_jsonc(oc_path.read_text(encoding="utf-8")))
    except json.JSONDecodeError as e:
        print(f"  WARNING: could not parse {oc_path}: {e}")
        return 0
    instructions = data.get("instructions", [])
    if not isinstance(instructions, list):
        return 0
    count = 0
    for ref in instructions:
        ref_path = Path(str(ref)).expanduser()
        if not ref_path.exists():
            print(f"  WARNING: instructions file not found, skipping: {ref_path}")
            continue
        backup_file(ref_path, backup_dir, dry, actions)
        body = ref_path.read_text(encoding="utf-8")
        note_id = slugify(f"imported-instructions-{ref_path.stem}")
        title = f"Imported instructions: {ref_path.name}"
        write_note(dest, note_id,
                   build_note(note_id, title, str(ref_path), body), dry, taken)
        count += 1
    return count


def import_claude_memory(mem_dir: Path | None, dest: Path, backup_dir: Path,
                         dry: bool, taken: set[str], actions: list) -> int:
    if not mem_dir or not mem_dir.exists():
        print("  (not found — skipped ~/.claude/memory)")
        return 0
    count = 0
    for md in sorted(mem_dir.glob("*.md")):
        backup_file(md, backup_dir, dry, actions)
        body = md.read_text(encoding="utf-8")
        note_id = slugify(f"imported-memory-{md.stem}")
        title = f"Imported memory: {md.stem}"
        write_note(dest, note_id,
                   build_note(note_id, title, str(md), body), dry, taken)
        count += 1
    return count


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    repo = Path(__file__).parent
    ap = argparse.ArgumentParser(
        description="Backup existing agent config and import it into a Cortex vault.")
    ap.add_argument("--vault", default=str(repo / "example-vault"),
                    help="Vault root to import into (default: bundled example-vault)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show what would happen without writing anything")
    ap.add_argument("--agents-md", help="Path to AGENTS.md (default: auto-detect)")
    ap.add_argument("--claude-md", help="Path to CLAUDE.md (default: auto-detect)")
    ap.add_argument("--opencode", help="Path to opencode.jsonc (default: auto-detect)")
    ap.add_argument("--claude-memory", help="Path to ~/.claude/memory dir (default: auto-detect)")
    args = ap.parse_args()

    vault = Path(args.vault).expanduser()
    if not vault.exists():
        sys.exit(f"ERROR: vault does not exist: {vault}")
    dest = vault / "feedback"
    dry = args.dry_run

    defaults = default_locations()
    agents_md = Path(args.agents_md).expanduser() if args.agents_md else first_existing(defaults["agents_md"])
    claude_md = Path(args.claude_md).expanduser() if args.claude_md else first_existing(defaults["claude_md"])
    opencode = Path(args.opencode).expanduser() if args.opencode else first_existing(defaults["opencode"])
    claude_mem = Path(args.claude_memory).expanduser() if args.claude_memory else first_existing(defaults["claude_memory_dir"])

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = vault / "_sync" / "backups" / stamp

    print(f"==> Cortex import  (vault: {vault})")
    print(f"    backup dir: {backup_dir}")
    if dry:
        print("    [DRY RUN] no files will be written")
    print()

    taken: set[str] = set()
    actions: list = []
    total = 0

    print("-- AGENTS.md")
    total += import_markdown_file(agents_md, "AGENTS.md", dest, backup_dir, dry, taken, actions)

    print("-- CLAUDE.md")
    total += import_markdown_file(claude_md, "CLAUDE.md", dest, backup_dir, dry, taken, actions)

    print("-- opencode instructions")
    total += import_opencode_instructions(opencode, dest, backup_dir, dry, taken, actions)

    print("-- Claude memory")
    total += import_claude_memory(claude_mem, dest, backup_dir, dry, taken, actions)

    # Write a manifest of what was backed up so cortex-uninstall.py can restore
    # original files (e.g. opencode.jsonc, which the distiller later rewrites).
    if actions and not dry:
        backup_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "source": "cortex-import",
            "created": datetime.now().isoformat(),
            "vault_root": str(vault),
            "actions": actions,
        }
        (backup_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"  import manifest -> {backup_dir / 'manifest.json'}")

    print()
    print(f"Imported {total} note(s) into {dest}")
    if total and not dry:
        print("Next steps:")
        print(f"  1. Review notes tagged 'review' in {dest} and adjust type/tier.")
        print(f"  2. Re-distill:  .venv/bin/python distill.py --config {vault}/_sync/cortex.yaml")


if __name__ == "__main__":
    main()

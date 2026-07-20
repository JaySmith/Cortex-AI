#! /usr/bin/env python3
"""
cortex.cli.commands.uninstall — Revert a machine to its pre-Cortex state.

Reads the install/import manifests that setup.sh and cortex-import.py leave in
<vault>/_sync/backups/ and undoes what Cortex added:

  - `created` files/dirs  -> deleted
  - `modified` / `backup` files -> restored from the backed-up copy

By design this KEEPS your vault notes (they're plain Markdown and yours). It only
removes Cortex's plumbing: generated cortex.yaml, the installed cortex-ai skill,
and any agent config Cortex rewrote (e.g. opencode.jsonc instructions).

Safe by default: prints a plan and changes NOTHING unless you pass --apply.

Usage:
  cortex uninstall --vault /path/to/vault --latest          # dry-run plan
  cortex uninstall --vault /path/to/vault --latest --apply  # do it
  cortex uninstall --vault /path/to/vault --backup 20260710-152233-setup --apply
  cortex uninstall --vault /path/to/vault --latest --apply --purge
      # also wipe _sync/distilled (a truly clean slate; notes still kept)
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


def find_manifests(vault: Path) -> list[Path]:
    """Return all manifest.json files under _sync/backups, newest-name last."""
    backups = vault / "_sync" / "backups"
    if not backups.exists():
        return []
    return sorted(backups.glob("*/manifest.json"))


def resolve_manifests(vault: Path, latest: bool, backup: str | None) -> list[Path]:
    manifests = find_manifests(vault)
    if not manifests:
        sys.exit(f"No install/import manifests found under {vault / '_sync' / 'backups'}")
    if backup:
        target = vault / "_sync" / "backups" / backup / "manifest.json"
        if not target.exists():
            sys.exit(f"Manifest not found: {target}")
        return [target]
    if latest:
        return [manifests[-1]]
    return list(reversed(manifests))


def restore_from(manifest_path: Path, action: dict, apply: bool) -> None:
    backup_dir = manifest_path.parent
    original = Path(action["path"])
    saved_as = action.get("saved_as")
    if not saved_as:
        print(f"  WARNING: no saved_as for {original} — cannot restore, skipping")
        return
    saved = backup_dir / saved_as
    if not saved.exists():
        print(f"  WARNING: backup copy missing: {saved} — skipping")
        return
    if not apply:
        print(f"  [DRY] restore {original}  <-  {saved.name}")
        return
    original.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(saved, original)
    print(f"  restored {original}")


def delete_created(action: dict, apply: bool) -> None:
    path = Path(action["path"])
    if not path.exists():
        print(f"  [skip] already gone: {path}")
        return
    if not apply:
        print(f"  [DRY] delete {path}")
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
        parent = path.parent
        if parent.name == "cortex-ai" and not any(parent.iterdir()):
            parent.rmdir()
    print(f"  removed {path}")


def process_manifest(manifest_path: Path, apply: bool) -> None:
    try:
        doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"  WARNING: could not read {manifest_path}: {e}")
        return
    actions = doc.get("actions", [])
    print(
        f"\n== manifest: {manifest_path.parent.name} "
        f"(cortex {doc.get('cortex_version', '?')}, {len(actions)} action(s)) =="
    )
    for a in actions:
        if a.get("op") in ("modified", "backup"):
            restore_from(manifest_path, a, apply)
    for a in actions:
        if a.get("op") == "created":
            delete_created(a, apply)


def purge_distilled(vault: Path, apply: bool) -> None:
    distilled = vault / "_sync" / "distilled"
    if not distilled.exists():
        return
    if not apply:
        print(f"\n[DRY] --purge would delete {distilled}")
        return
    shutil.rmtree(distilled)
    print(f"\npurged {distilled}")


def run_uninstall(
    vault: Path,
    latest: bool = True,
    backup: str | None = None,
    apply: bool = False,
    purge: bool = False,
) -> int:
    """Run the uninstall operation. Returns exit code (0 = ok)."""
    if not vault.exists():
        print(f"ERROR: vault does not exist: {vault}", file=sys.stderr)
        return 1

    manifests = resolve_manifests(vault, latest, backup)

    mode = "APPLY" if apply else "DRY-RUN (nothing will change)"
    print(f"==> Cortex uninstall [{mode}]")
    print(f"    vault: {vault}")
    print(f"    manifests to process: {len(manifests)}")
    print("    NOTE: your vault notes are NOT touched.")

    for m in manifests:
        process_manifest(m, apply)

    if purge:
        purge_distilled(vault, apply)

    print()
    if apply:
        print("Done. Cortex plumbing removed; your notes remain in the vault.")
        print("You may also want to remove the MCP 'cortex' entry from your agent config,")
        print("and delete the cloned cortex-distiller repo if you no longer need it.")
    else:
        print("Dry-run complete. Re-run with --apply to make these changes.")

    return 0


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Revert Cortex changes using install/import manifests. Keeps your vault notes."
        )
    )
    ap.add_argument(
        "--vault",
        required=True,
        help="Vault root Cortex was installed against",
    )
    group = ap.add_mutually_exclusive_group()
    group.add_argument(
        "--latest",
        action="store_true",
        help="Undo only the most recent manifest",
    )
    group.add_argument(
        "--backup",
        help="Undo a specific backup dir name (e.g. 20260710-152233-setup)",
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Actually make changes (default is a dry-run plan)",
    )
    ap.add_argument(
        "--purge",
        action="store_true",
        help=("Also delete _sync/distilled (generated output). Notes are still kept."),
    )
    args = ap.parse_args()

    vault = Path(args.vault).expanduser()
    rc = run_uninstall(
        vault=vault,
        latest=args.latest or args.backup is None,
        backup=args.backup,
        apply=args.apply,
        purge=args.purge,
    )
    sys.exit(rc)


if __name__ == "__main__":
    main()

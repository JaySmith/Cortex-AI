#!/usr/bin/env python3
"""
distill.py — Sync an Obsidian vault to agent-specific formats.

TIERED MODEL (driven by each note's `tier` frontmatter):
  core           -> eager: concatenated into a single core-context.md
  <custom-name>  -> any string listed in eager_tiers is also eager (e.g. "jira")
  skill:<name>   -> lazy: distilled body embedded into skills/<name>/reference.md
  project        -> lazy: written to distilled/opencode/projects/<id>.md
  vault-only     -> never distilled.

Config is read from cortex.yaml (co-located with this script by default;
in a normal install it lives at <vault>/_sync/cortex.yaml).

Usage:
  python3 distill.py                        # sync all enabled targets
  python3 distill.py --dry-run              # show changes without writing
  python3 distill.py --list                 # list all vault notes with tier
  python3 distill.py --show-config          # print resolved paths as JSON
  python3 distill.py --purge                # preview drained log/session deletions
  python3 distill.py --purge-apply          # delete drained logs/sessions + rebuild
  python3 distill.py --config /path/to.yaml # use a specific config file
"""

# --- venv bootstrap -------------------------------------------------------
# distill.py requires PyYAML which lives in the sibling .venv, not system
# Python (macOS Homebrew Python is externally-managed and can't have packages
# installed into it). If we're not already running inside that venv, re-exec
# ourselves with its interpreter. os.execv replaces the current process image
# outright — no subprocess overhead, and the exact-path check guards against
# an infinite loop. If no venv exists we fall through and let the yaml
# ImportError below fire naturally. Cross-platform: Windows uses
# .venv/Scripts/python.exe, POSIX uses .venv/bin/python.
import sys as _sys, os as _os
from pathlib import Path as _Path


def _reexec_with_venv() -> None:
    sync = _Path(__file__).resolve().parent
    venv_dir = sync / ".venv"
    if _sys.platform == "win32":
        venv_py = venv_dir / "Scripts" / "python.exe"
    else:
        venv_py = venv_dir / "bin" / "python"
    if not venv_py.exists():
        return  # no venv — let the yaml ImportError fire naturally below
    # Detect whether we're already running inside this venv. We can't compare
    # sys.executable to venv_py because the venv's python is often a symlink to
    # the same real interpreter as system Python — the resolved paths match even
    # though the venv's site-packages (PyYAML) is only on sys.path when launched
    # via the venv binary. sys.prefix, however, points at the venv dir when and
    # only when we're actually running inside it.
    if _Path(_sys.prefix).resolve() == venv_dir.resolve():
        return  # already running inside the venv — nothing to do
    _os.execv(str(venv_py), [str(venv_py)] + _sys.argv)


_reexec_with_venv()
del _reexec_with_venv, _sys, _os, _Path
# --- end venv bootstrap ---------------------------------------------------

import sys
import re
import json
import hashlib
import argparse
from pathlib import Path
from datetime import datetime
from typing import Callable

try:
    import yaml
except ImportError:
    sys.exit(
        "ERROR: PyYAML is required.\n"
        "  pip install -r requirements.txt"
    )

from hive_client import HubClient, HubConnectionError


# ---------------------------------------------------------------------------
# Versioning
#
# Two independent numbers with different jobs:
#
#   VERSION         SemVer release string (e.g. "1.0.0") — a human-facing label
#                   for "which release of the Cortex toolchain is this". Bumped
#                   per the rules in CHANGELOG.md / docs (MAJOR/MINOR/PATCH).
#
#   SCHEMA_VERSION  plain integer (e.g. 1) — the on-disk data contract for the
#                   vault + distilled output (memory.json shape, cortex.yaml
#                   required keys, required frontmatter). Bumped by +1 ONLY when
#                   that contract changes, and each bump gets a migration below.
#                   This is what upgrade-safety compares — never the SemVer.
# ---------------------------------------------------------------------------

def cortex_version() -> str:
    """Read the Cortex release version from the repo-root VERSION file (fallback 'unknown')."""
    vf = Path(__file__).parent / "VERSION"
    try:
        return vf.read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


def schema_version() -> int:
    """Read the on-disk schema version this code understands (fallback 1)."""
    sf = Path(__file__).parent / "SCHEMA_VERSION"
    try:
        return int(sf.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return 1


# ---------------------------------------------------------------------------
# Migrations
#
# Registry mapping a starting schema version to the step that upgrades it by +1.
# Each entry: from_version -> (to_version, description, fn(vault_path) -> None).
# Functions MUST be idempotent and only touch _sync/ contents (config +
# distilled output); user notes are never modified by a migration.
#
# There are no migrations at schema 1 — the machinery exists so the first
# breaking change is a small addition rather than a redesign.
# ---------------------------------------------------------------------------

def _migrate_1_to_2(vault_path: Path) -> None:
    """Add hive block to cortex.yaml if missing (schema v1 -> v2)."""
    cfg_file = vault_path / "_sync" / "cortex.yaml"
    if not cfg_file.exists():
        return
    text = cfg_file.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError:
        return
    if not isinstance(data, dict):
        return
    if "hive" in data:
        return  # already has hive block
    data["hive"] = {
        "enabled": False,
        "hub_url": "http://localhost:4096/mcp",
        "machine_id": "",
        "hub_token": "",
        "replicate_tiers": ["core", "skill:*", "project"],
        "sync_interval": 300,
    }
    # Preserve original file's YAML formatting where possible
    text_lower = text.rstrip()
    hive_yaml = (
        "\n\n# --- Added by schema v2 migration ---\n"
        "hive:\n"
        "  enabled: false\n"
        '  hub_url: "http://localhost:4096/mcp"\n'
        '  machine_id: ""\n'
        '  hub_token: ""\n'
        "  replicate_tiers:\n"
        "    - core\n"
        '    - "skill:*"\n'
        "    - project\n"
        "  sync_interval: 300\n"
    )
    cfg_file.write_text(text_lower + hive_yaml, encoding="utf-8")
    print(f"    added hive block to {cfg_file}")


MIGRATIONS: dict[int, tuple[int, str, Callable[[Path], None]]] = {
    1: (2, "add hive config block to cortex.yaml", _migrate_1_to_2),
}


def read_vault_schema(vault_path: Path) -> int | None:
    """Return the schema version recorded in the vault's memory.json, or None if unknown/absent."""
    for candidate in (
        vault_path / "_sync" / "distilled" / "memory.json",
    ):
        if candidate.exists():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                sv = data.get("_meta", {}).get("schema_version")
                return int(sv) if sv is not None else None
            except (OSError, ValueError, json.JSONDecodeError):
                return None
    return None


def check_and_migrate(vault_path: Path, dry: bool) -> None:
    """Compare code schema vs vault schema and reconcile.

    - equal / vault unknown (fresh)   -> proceed
    - code newer than vault           -> back up _sync/, run migrations, proceed
    - code older than vault           -> refuse (no silent downgrade)
    """
    code_schema = schema_version()
    vault_schema = read_vault_schema(vault_path)

    if vault_schema is None:
        return  # fresh vault or pre-schema output; distill will stamp it

    if vault_schema == code_schema:
        return

    if vault_schema > code_schema:
        sys.exit(
            f"ERROR: vault schema is v{vault_schema} but this Cortex code only "
            f"understands v{code_schema}.\n"
            f"       Your data is newer than the code. Update Cortex (git pull) "
            f"before running.\n"
            f"       Refusing to run to avoid corrupting your vault."
        )

    # code_schema > vault_schema: run migrations step by step.
    print(f"==> Schema migration needed: v{vault_schema} -> v{code_schema}")
    if not dry:
        backup_sync_dir(vault_path, reason="migration")

    current = vault_schema
    while current < code_schema:
        step = MIGRATIONS.get(current)
        if step is None:
            sys.exit(
                f"ERROR: no migration registered from schema v{current}. "
                f"Cannot safely upgrade. Report this."
            )
        to_v, desc, fn = step
        print(f"    migrating v{current} -> v{to_v}: {desc}")
        if not dry:
            fn(vault_path)
        current = to_v
    print(f"    migration complete (now v{code_schema})")


def backup_sync_dir(vault_path: Path, reason: str = "backup") -> Path:
    """Snapshot the vault's _sync/ (config + distilled + memory.json) into a
    timestamped backup folder. Returns the backup path. Notes are NOT copied —
    only the generated/plumbing files that a migration or upgrade might change.
    """
    import shutil
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = vault_path / "_sync" / "backups" / f"{stamp}-{reason}"
    backup_root.mkdir(parents=True, exist_ok=True)
    sync_dir = vault_path / "_sync"
    for item in ("cortex.yaml", "distilled", "last-sync.json"):
        src = sync_dir / item
        if not src.exists():
            continue
        dst = backup_root / item
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
    print(f"    backed up _sync/ -> {backup_root}")
    return backup_root


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def load_config(config_file: Path) -> dict:
    if not config_file.exists():
        sys.exit(f"ERROR: Config not found: {config_file}")
    text = config_file.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        sys.exit(f"ERROR: Failed to parse {config_file}: {e}")
    data = data or {}
    # Apply hive defaults — hive block may be absent in pre-1.3 configs
    hive = data.get("hive", {})
    hive.setdefault("enabled", False)
    hive.setdefault("hub_url", "http://localhost:4096/mcp")
    hive.setdefault("machine_id", "")
    hive.setdefault("hub_token", "")
    hive.setdefault("replicate_tiers", ["core", "skill:*", "project"])
    hive.setdefault("sync_interval", 300)
    data["hive"] = hive
    return data


def validate_target_config(name: str, cfg: dict, required_keys: list[str]) -> bool:
    """Return True if all required keys are present; print an error and return False otherwise."""
    for key in required_keys:
        if key not in cfg:
            print(f"  ERROR: target '{name}' is missing required config key '{key}' — skipping.")
            return False
    return True


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------

def parse_frontmatter(content: str) -> tuple[dict, str]:
    if not content.startswith("---"):
        return {}, content
    end = content.find("\n---", 3)
    if end == -1:
        return {}, content
    yaml_block = content[3:end].strip("\n")
    body = content[end + 4:].strip()
    try:
        meta = yaml.safe_load(yaml_block)
    except yaml.YAMLError:
        return {}, body
    if not isinstance(meta, dict):
        return {}, body
    return meta, body


def strip_wiki_links(text: str) -> str:
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    return text


def extract_wiki_links(text: str) -> list[str]:
    """Extract target ids from [[wiki-link]] syntax in a note body.

    Handles both [[target]] and [[target|display text]] forms.
    Returns the raw target strings (which may be ids or display names).
    """
    links = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", text)
    return links


def strip_leading_h1(text: str) -> str:
    """Drop a note body's own leading `# Title`.

    The distiller already emits a heading (`## {title}` for core/skills,
    `# {title}` for projects) before the body, so the body's own H1 is a
    redundant duplicate. Only strips an H1 that appears before any other
    content, then swallows the blank line that follows it.
    """
    stripped = text.lstrip("\n")
    if not stripped.startswith("# "):
        return text
    parts = stripped.split("\n", 1)
    rest = parts[1] if len(parts) > 1 else ""
    return rest.lstrip("\n")


def strip_related_section(text: str) -> str:
    """Drop a trailing `## Related` section.

    Related links are vault-navigation aids (they point at other notes by id);
    in always-loaded distilled context they're dead weight. Removes the
    `## Related` heading and everything after it to the end of the note.
    """
    return re.sub(r"\n#+\s+Related\b.*\Z", "", text, flags=re.IGNORECASE | re.DOTALL).rstrip()


# ---------------------------------------------------------------------------
# Vault note
# ---------------------------------------------------------------------------

class VaultNote:
    @staticmethod
    def _as_str(v: object) -> str:
        # pyyaml may parse dates/ints natively; normalise everything to str.
        if v is None:
            return ""
        return str(v)

    @staticmethod
    def _as_list(v: object) -> list[str]:
        if v is None or v == "":
            return []
        if isinstance(v, list):
            return [str(x) for x in v]
        return [str(v)]

    def __init__(self, path: Path, meta: dict, body: str) -> None:
        self.path = path
        self.meta = meta
        self.body = body
        self.name: str = self._as_str(meta.get("id")) or path.stem
        self.note_type: str = self._as_str(meta.get("type")) or "unknown"
        self.category: str = self._as_str(meta.get("category"))
        self.tier: str = self._as_str(meta.get("tier"))
        self.tags: list[str] = self._as_list(meta.get("tags"))
        self.agents: list[str] = self._as_list(meta.get("agents"))
        self.aliases: list[str] = self._as_list(meta.get("aliases"))
        self.updated: str = self._as_str(meta.get("updated"))
        self.drained: bool = meta.get("drained") is True  # log/session lessons extracted -> safe to purge
        self.expires_at: str = self._as_str(meta.get("expires_at"))  # ISO date; empty = never
        self.hive: bool | None = None  # None = use tier default, True = force sync, False = never sync
        raw_hive = meta.get("hive")
        if raw_hive is True:
            self.hive = True
        elif raw_hive is False:
            self.hive = False

    def is_expired(self) -> bool:
        """Return True if this note has a past expires_at date."""
        if not self.expires_at:
            return False
        try:
            exp = datetime.strptime(self.expires_at, "%Y-%m-%d")
            return datetime.now() > exp
        except ValueError:
            return False

    def title(self) -> str:
        if self.aliases:
            return self.aliases[0]
        return self.name.replace("-", " ").title()

    def clean_body(
        self,
        strip_links: bool = True,
        drop_h1: bool = True,
        drop_related: bool = False,
    ) -> str:
        body = self.body
        if strip_links:
            body = strip_wiki_links(body)
        if drop_h1:
            body = strip_leading_h1(body)
        if drop_related:
            body = strip_related_section(body)
        return body

    def to_dict(self) -> dict:
        d = {
            "id": self.name,
            "type": self.note_type,
            "category": self.category,
            "tier": self.tier,
            "tags": self.tags,
            "updated": self.updated,
            "aliases": self.aliases,
            "content": strip_wiki_links(self.body),
        }
        if self.expires_at:
            d["expires_at"] = self.expires_at
        return d


def scan_vault(vault_path: Path, skip_dirs: set[str] | None = None) -> list[VaultNote]:
    """Scan vault_path recursively, returning all notes that have a 'type' field."""
    if skip_dirs is None:
        skip_dirs = {"templates"}

    notes: list[VaultNote] = []
    seen_ids: dict[str, Path] = {}

    for md in vault_path.rglob("*.md"):
        rel = md.relative_to(vault_path)
        parts = rel.parts
        # Skip dot-dirs, underscore dirs, and user-configured skip_dirs
        if any(p.startswith(".") or p.startswith("_") for p in parts):
            continue
        if parts[0] in skip_dirs:
            continue
        try:
            content = md.read_text(encoding="utf-8")
        except Exception as e:
            print(f"  WARNING: Could not read {md}: {e}")
            continue
        meta, body = parse_frontmatter(content)
        if not meta.get("type"):
            continue
        note = VaultNote(md, meta, body)
        # Duplicate ID detection
        if note.name in seen_ids:
            print(
                f"  WARNING: duplicate id '{note.name}' in {note.path} "
                f"(first seen at {seen_ids[note.name]}) — both kept, last write wins in dict targets"
            )
        else:
            seen_ids[note.name] = note.path
        notes.append(note)
    return notes


def excluded(note: VaultNote, exclude_tags: set[str], vault_only_types: set[str]) -> bool:
    if note.note_type in vault_only_types:
        return True
    return bool(set(note.tags) & exclude_tags)


# ---------------------------------------------------------------------------
# Graph extraction — parse [[wiki-links]] into a directed edge list
# ---------------------------------------------------------------------------

def build_wiki_graph(notes: list[VaultNote]) -> dict:
    """Parse [[wiki-links]] from all note bodies into a directed graph.

    Returns a dict with:
      - nodes: [{id, type, category, degree}]
      - edges: [{source, target}]
      - dangling: [{note, target}]  (links pointing to non-existent notes)
      - isolated: [note_id]  (notes with zero inbound or outbound links)
      - god_nodes: [{id, degree}]  (notes with degree > median + 2*stdev)
    """
    # Build a lookup from note id -> note for resolving links
    id_set = {n.name for n in notes}
    id_aliases: dict[str, str] = {}  # alias -> canonical id
    for n in notes:
        for alias in n.aliases:
            id_aliases[alias.lower()] = n.name

    edges: list[dict] = []
    dangling: list[dict] = []
    out_degree: dict[str, int] = {n.name: 0 for n in notes}
    in_degree: dict[str, int] = {n.name: 0 for n in notes}

    for n in notes:
        raw_links = extract_wiki_links(n.body)
        seen_targets: set[str] = set()
        for target in raw_links:
            # Resolve: direct id match, alias match, or case-insensitive id match
            resolved = target
            if target not in id_set:
                resolved = id_aliases.get(target.lower(), "")
            if not resolved:
                # Try case-insensitive id match
                lower_target = target.lower()
                for nid in id_set:
                    if nid.lower() == lower_target:
                        resolved = nid
                        break
            if not resolved:
                dangling.append({"note": n.name, "target": target})
                continue
            if resolved == n.name:
                continue  # skip self-links
            if resolved in seen_targets:
                continue  # dedupe per-note
            seen_targets.add(resolved)
            edges.append({"source": n.name, "target": resolved})
            out_degree[n.name] = out_degree.get(n.name, 0) + 1
            in_degree[resolved] = in_degree.get(resolved, 0) + 1

    # Compute total degree for each node
    total_degree = {}
    for nid in id_set:
        total_degree[nid] = out_degree.get(nid, 0) + in_degree.get(nid, 0)

    # Isolated nodes (degree == 0)
    isolated = sorted(nid for nid, d in total_degree.items() if d == 0)

    # God nodes: degree > median + 2*stdev
    degrees = sorted(total_degree.values())
    if degrees:
        median = degrees[len(degrees) // 2]
        mean = sum(degrees) / len(degrees)
        variance = sum((d - mean) ** 2 for d in degrees) / len(degrees)
        stdev = variance ** 0.5
        threshold = median + 2 * stdev
    else:
        threshold = 0
    god_nodes = sorted(
        [{"id": nid, "degree": d} for nid, d in total_degree.items() if d > threshold],
        key=lambda x: x["degree"],
        reverse=True,
    )

    # Nodes with metadata
    nodes = [
        {
            "id": n.name,
            "type": n.note_type,
            "category": n.category,
            "degree": total_degree.get(n.name, 0),
        }
        for n in notes
    ]

    return {
        "nodes": nodes,
        "edges": edges,
        "dangling": dangling,
        "isolated": isolated,
        "god_nodes": god_nodes,
    }


# ---------------------------------------------------------------------------
# Targets
# ---------------------------------------------------------------------------

def write_file(path: Path, content: str, dry: bool) -> None:
    """Write content to path, skipping if content is already identical."""
    if dry:
        print(f"  [DRY] write {path} ({len(content)} chars)")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        print(f"  unchanged {path}")
        return
    path.write_text(content, encoding="utf-8")
    print(f"  wrote {path} ({len(content)} chars)")


def sync_core_context(
    notes: list[VaultNote],
    cfg: dict,
    eager_tiers: list[str],
    strip_links: bool,
    dry: bool,
) -> Path | None:
    if not validate_target_config("core_context", cfg, ["output_file"]):
        return None
    out = Path(cfg["output_file"])
    eager = [n for n in notes if n.tier in eager_tiers]
    eager.sort(key=lambda n: (eager_tiers.index(n.tier), n.name))
    print(f"\n--- core-context: {len(eager)} eager notes ({', '.join(eager_tiers)}) ---")

    parts = [
        "# Core Context (auto-generated by distill.py — do not edit)",
        "",
        "Always-loaded memory. Heavy/specialised knowledge is loaded on demand via skills.",
        "",
    ]
    for n in eager:
        parts.append(f"## {n.title()}")
        parts.append("")
        parts.append(n.clean_body(strip_links, drop_related=True))
        parts.append("")

    # On-demand pointer index
    skill_topics: dict[str, list[str]] = {}
    project_notes: list[VaultNote] = []
    for n in notes:
        if n.tier.startswith("skill:"):
            skill_topics.setdefault(n.tier.split(":", 1)[1], []).append(n.title())
        elif n.tier == "project":
            project_notes.append(n)

    if skill_topics or project_notes:
        parts.append("## On-Demand Memory (load only when relevant)")
        parts.append("")
        if skill_topics:
            parts.append("Specialized knowledge lives in skills. Invoke the skill and read its `reference.md`:")
            parts.append("")
            for skill in sorted(skill_topics):
                topics = ", ".join(sorted(skill_topics[skill]))
                parts.append(f"- **{skill}** skill — {topics}")
            parts.append("")
        if project_notes:
            proj_dir = out.parent / "projects"
            parts.append("Project context (read the file when the project comes up):")
            parts.append("")
            for n in sorted(project_notes, key=lambda x: x.name):
                parts.append(f"- **{n.title()}** — `{proj_dir / (n.name + '.md')}`")
            parts.append("")

    content = "\n".join(parts).rstrip() + "\n"
    write_file(out, content, dry)
    return out


def sync_skill_embeds(
    notes: list[VaultNote],
    cfg: dict,
    strip_links: bool,
    dry: bool,
) -> list[str]:
    if not validate_target_config("skills", cfg, ["skills_dir"]):
        return []
    skills_dir = Path(cfg["skills_dir"])
    embed_name = cfg.get("embed_filename", "reference.md")
    by_skill: dict[str, list[VaultNote]] = {}
    for n in notes:
        if n.tier.startswith("skill:"):
            by_skill.setdefault(n.tier.split(":", 1)[1], []).append(n)
    print(f"\n--- skill-embeds: {sum(len(v) for v in by_skill.values())} notes -> {len(by_skill)} skills ---")
    written: list[str] = []
    for skill, ns in sorted(by_skill.items()):
        target_dir = skills_dir / skill
        if not target_dir.exists():
            print(f"  WARNING: skill dir missing, skipping: {target_dir}")
            continue
        ns.sort(key=lambda n: n.name)
        parts = [
            f"# {skill} — Reference (auto-generated by distill.py — do not edit)",
            "",
            "Distilled memory for this skill. Loaded only when the skill is invoked.",
            "",
        ]
        for n in ns:
            parts.append(f"## {n.title()}")
            parts.append("")
            parts.append(n.clean_body(strip_links))
            parts.append("")
        content = "\n".join(parts).rstrip() + "\n"
        write_file(target_dir / embed_name, content, dry)
        written.append(skill)
    return written


def sync_projects(
    notes: list[VaultNote],
    cfg: dict,
    strip_links: bool,
    dry: bool,
) -> Path | None:
    if not validate_target_config("projects", cfg, ["output_dir"]):
        return None
    out_dir = Path(cfg["output_dir"])
    projs = [n for n in notes if n.tier == "project"]
    print(f"\n--- project-context: {len(projs)} notes ---")
    if not dry:
        out_dir.mkdir(parents=True, exist_ok=True)
    keep: set[str] = set()
    for n in sorted(projs, key=lambda n: n.name):
        fn = f"{n.name}.md"
        keep.add(fn)
        parts = [f"# {n.title()}", "", n.clean_body(strip_links), ""]
        write_file(out_dir / fn, "\n".join(parts).rstrip() + "\n", dry)
    # Prune stale project files
    if out_dir.exists():
        for f in out_dir.glob("*.md"):
            if f.name not in keep:
                if dry:
                    print(f"  [DRY] prune stale {f}")
                else:
                    f.unlink()
                    print(f"  pruned stale {f}")
    return out_dir


def sync_python_agents(
    notes: list[VaultNote],
    cfg: dict,
    exclude_tags: list[str],
    vault_only_types: list[str],
    dry: bool,
) -> None:
    if not validate_target_config("python-agents", cfg, ["output_file"]):
        return
    out = Path(cfg["output_file"])
    inc: list[str] = cfg.get("include_types", [])
    extra_excl: list[str] = cfg.get("exclude_tags", [])

    # Pre-compute merged exclusion sets once — avoids per-note list concatenation
    all_exclude: set[str] = set(exclude_tags) | set(extra_excl)
    vault_only_set: set[str] = set(vault_only_types)

    matching = [
        n for n in notes
        if n.note_type in inc and not excluded(n, all_exclude, vault_only_set)
    ]
    print(f"\n--- python-agents (json): {len(matching)} notes ---")
    # Build wiki-link graph for inclusion in memory.json
    graph = build_wiki_graph(notes)
    # Build adjacency lookup for graph-enhanced relatedness
    adjacency: dict[str, list[str]] = {}
    for edge in graph["edges"]:
        adjacency.setdefault(edge["source"], []).append(edge["target"])
        adjacency.setdefault(edge["target"], []).append(edge["source"])
    result = {
        "_meta": {
            "generated": datetime.now().isoformat(),
            "source": "Cortex vault",
            "cortex_version": cortex_version(),
            "schema_version": schema_version(),
            "count": len(matching),
            "graph_edges": len(graph["edges"]),
            "graph_dangling": len(graph["dangling"]),
            "graph_isolated": len(graph["isolated"]),
        },
        "notes": {n.name: n.to_dict() for n in sorted(matching, key=lambda n: n.name)},
        "_graph": {
            "edges": graph["edges"],
            "adjacency": adjacency,
        },
    }
    write_file(out, json.dumps(result, indent=2, ensure_ascii=False), dry)


def prune_distilled_opencode(core_out: Path, dry: bool) -> None:
    """Remove legacy flat distilled files superseded by core-context + projects/.

    WARNING: This deletes ANY .md file in core_out.parent that is not core-context.md.
    Only enable via prune_legacy: true in config if you are certain no other files
    live in that directory.
    """
    d = core_out.parent
    if not d.exists():
        return
    keep = {core_out.name}
    for f in d.glob("*.md"):
        if f.name in keep:
            continue
        if dry:
            print(f"  [DRY] prune legacy distilled {f}")
        else:
            f.unlink()
            print(f"  pruned legacy distilled {f}")


def update_opencode_instructions(opencode_cfg_path: Path, core_out: Path, dry: bool) -> None:
    """Set opencode instructions to reference ONLY the core-context file."""
    if not opencode_cfg_path.exists():
        print(f"  WARNING: opencode config not found: {opencode_cfg_path}")
        return
    text = opencode_cfg_path.read_text(encoding="utf-8")
    core_path_str = str(core_out)
    new_block = (
        '"instructions": [\n'
        f'    "{core_path_str}"\n'
        '  ]'
    )
    pattern = re.compile(r'"instructions"\s*:\s*\[.*?\]', re.DOTALL)
    if pattern.search(text):
        new_text = pattern.sub(new_block, text, count=1)
        action = "updated"
    else:
        # Attempt to insert after a known anchor key
        new_text = text.replace('"lsp": true,', '"lsp": true,\n  ' + new_block + ',', 1)
        if new_text == text:
            # Anchor not found — cannot safely insert; tell the user what to add manually
            print(
                f"  WARNING: Could not insert 'instructions' into {opencode_cfg_path}.\n"
                f"           No existing 'instructions' key and no 'lsp' anchor found.\n"
                f"           Add manually:\n"
                f'             "instructions": ["{core_path_str}"]'
            )
            return
        action = "inserted"

    if new_text == text:
        print("  opencode instructions unchanged (skipped write)")
        return

    if dry:
        print(f"  [DRY] would {action} opencode instructions -> [core-context.md]")
    else:
        opencode_cfg_path.write_text(new_text, encoding="utf-8")
        print(f"  {action} opencode instructions -> [core-context.md]")


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def save_sync_state(vault_path: Path, notes: list[VaultNote]) -> None:
    state_file = vault_path / "_sync" / "last-sync.json"
    state = {
        "timestamp": datetime.now().isoformat(),
        "note_count": len(notes),
        "notes": {
            n.name: {
                "path": str(n.path.relative_to(vault_path)),
                "type": n.note_type,
                "tier": n.tier,
                "updated": n.updated,
                "hash": hashlib.md5(n.body.encode()).hexdigest(),
            }
            for n in notes
        },
    }
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Purge — delete spent session artifacts
#
# A `log` or `session` note flagged `drained: true` has had its durable lessons
# extracted into knowledge/entity notes (that's what the sync capture step does),
# so the raw session file is now dead weight. Purge deletes those files and
# nothing else: only types log/session, only when drained is explicitly true.
# Dry-run by default; the caller re-runs distillation after an apply so the
# distilled outputs and last-sync.json reflect the smaller vault.
# ---------------------------------------------------------------------------

PURGEABLE_TYPES = ("log", "session")


def find_drained_notes(notes: list[VaultNote]) -> list[VaultNote]:
    """Return notes eligible for purge: type in PURGEABLE_TYPES and drained is true."""
    return [
        n for n in notes
        if n.note_type in PURGEABLE_TYPES and n.drained
    ]


def purge_drained_logs(vault_path: Path, apply: bool) -> list[VaultNote]:
    """Delete drained log/session notes from the vault.

    apply=False (default) previews; apply=True deletes the files. Returns the
    list of notes that were (or would be) deleted. The caller is responsible for
    re-running distillation after an apply.
    """
    skip_dirs: set[str] = {"templates"}
    notes = scan_vault(vault_path, skip_dirs)
    drained = find_drained_notes(notes)

    print(f"\n--- purge: {len(drained)} drained log/session note(s) ---")
    if not drained:
        print("  nothing to purge (no notes flagged drained: true)")
        return []

    for n in drained:
        rel = n.path.relative_to(vault_path)
        if apply:
            n.path.unlink()
            print(f"  deleted {rel}")
        else:
            print(f"  [DRY] would delete {rel}  (type={n.note_type})")

    if not apply:
        print("\n  [DRY RUN] No files were deleted. Re-run with --purge-apply to delete.")
    return drained


# ---------------------------------------------------------------------------
# --show-config
# ---------------------------------------------------------------------------

def show_config(cfg: dict, cfg_path: Path) -> None:
    """Print resolved Cortex paths as JSON so callers (skill/setup) can discover them."""
    targets: dict = cfg.get("targets", {})
    cc = targets.get("core_context", {})
    pa = targets.get("python-agents", {})
    sk = targets.get("skills", {})
    pr = targets.get("projects", {})

    vault_schema = None
    vp = cfg.get("vault_path", "")
    if vp:
        vault_schema = read_vault_schema(Path(vp))

    resolved = {
        "cortex_version": cortex_version(),
        "schema_version": schema_version(),
        "vault_schema_version": vault_schema,
        "config_file": str(cfg_path.resolve()),
        "vault_path": cfg.get("vault_path", ""),
        "distill_py": str(Path(__file__).resolve()),
        "core_context": cc.get("output_file", ""),
        "memory_json": pa.get("output_file", ""),
        "skills_dir": sk.get("skills_dir", ""),
        "projects_dir": pr.get("output_dir", ""),
        "hive_enabled": cfg.get("hive", {}).get("enabled", False),
        "hive_hub_url": cfg.get("hive", {}).get("hub_url", ""),
        "hive_machine_id": cfg.get("hive", {}).get("machine_id", ""),
    }
    print(json.dumps(resolved, indent=2, ensure_ascii=False))


def run_check(vault_path: Path) -> None:
    """Human-readable health/version report. Exits non-zero if a downgrade is detected."""
    code_v = cortex_version()
    code_schema = schema_version()
    vault_schema = read_vault_schema(vault_path)

    print(f"Cortex release version : {code_v}")
    print(f"Code schema version    : {code_schema}")
    print(f"Vault schema version   : {vault_schema if vault_schema is not None else '(none — fresh)'}")

    if vault_schema is None:
        print("Status                 : OK — fresh vault; first distill will stamp schema.")
        return
    if vault_schema == code_schema:
        print("Status                 : OK — schema in sync.")
        return
    if vault_schema < code_schema:
        print(f"Status                 : MIGRATION PENDING (v{vault_schema} -> v{code_schema}).")
        print("                         Run distill to migrate (auto-backs up _sync/ first).")
        return
    # vault newer than code
    print("Status                 : ERROR — vault is NEWER than this code.")
    print("                         Update Cortex (git pull) before running.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Hive — shared vault via cortex-hub
# ---------------------------------------------------------------------------

def hive_eligible(note: VaultNote, config: dict) -> bool:
    """Check if a note should sync to hub based on frontmatter + config tiers."""
    if note.hive is True:
        return True
    if note.hive is False:
        return False
    replicate = config.get("hive", {}).get("replicate_tiers", [])
    for tier_pattern in replicate:
        if tier_pattern.endswith("*"):
            if note.tier.startswith(tier_pattern[:-1]):
                return True
        elif note.tier == tier_pattern:
            return True
    return False


def hive_push(config: dict, notes: list[VaultNote] | None = None) -> int:
    """Push eligible notes to hub. Returns count of pushed notes.

    If notes is None, scans the vault fresh.
    """
    hive_cfg = config.get("hive", {})
    if not hive_cfg.get("enabled"):
        sys.exit("ERROR: hive is not enabled in cortex.yaml")
    machine_id = hive_cfg.get("machine_id", "")
    if not machine_id:
        sys.exit("ERROR: hive.machine_id is not set in cortex.yaml")

    if notes is None:
        vault = Path(config["vault_path"])
        skip_dirs: set[str] = set(config.get("skip_dirs", ["templates"]))
        notes = scan_vault(vault, skip_dirs)

    client = HubClient(
        hive_cfg["hub_url"],
        token=hive_cfg.get("hub_token", ""),
    )
    client.connect()
    pushed = 0
    for note in notes:
        if not hive_eligible(note, config):
            continue
        key = f"vault/{machine_id}/{note.name}"
        value = json.dumps({
            "id": note.name,
            "type": note.note_type,
            "category": note.category,
            "tier": note.tier,
            "tags": note.tags,
            "aliases": note.aliases,
            "updated": note.updated,
            "content": note.clean_body(strip_links=True, drop_h1=True, drop_related=True),
            "machine_id": machine_id,
        })
        tags = ["vault", machine_id, note.tier]
        if note.note_type:
            tags.append(note.note_type)
        client.memory_set(key, value, tags)
        pushed += 1
    client.close()
    return pushed


def hive_pull(config: dict) -> int:
    """Pull vault notes from hub. Newest timestamp wins. Returns count pulled."""
    hive_cfg = config.get("hive", {})
    if not hive_cfg.get("enabled"):
        sys.exit("ERROR: hive is not enabled in cortex.yaml")
    machine_id = hive_cfg.get("machine_id", "")
    if not machine_id:
        sys.exit("ERROR: hive.machine_id is not set in cortex.yaml")

    client = HubClient(
        hive_cfg["hub_url"],
        token=hive_cfg.get("hub_token", ""),
    )
    client.connect()
    vault_root = Path(config["vault_path"])
    results = client.memory_search("vault/")
    client.close()

    if not results:
        return 0

    pulled = 0
    for entry in results:
        try:
            note_data = json.loads(entry["value"]) if isinstance(entry.get("value"), str) else entry.get("value", {})
        except (json.JSONDecodeError, ValueError):
            continue
        # Skip notes from this machine
        if note_data.get("machine_id") == machine_id:
            continue
        # Determine local path: preserve original directory structure
        note_id = note_data.get("id", "")
        # Search for existing local file with this id
        local_path = None
        for md in vault_root.rglob("*.md"):
            meta, _ = parse_frontmatter(md.read_text(encoding="utf-8", errors="replace"))
            if meta.get("id") == note_id:
                local_path = md
                break
        if local_path is None:
            # New note — write to a sensible location based on type
            note_type = note_data.get("type", "knowledge")
            type_dir = vault_root / (note_type + "s" if not note_type.endswith("s") else note_type)
            type_dir.mkdir(parents=True, exist_ok=True)
            local_path = type_dir / f"{note_id}.md"
        # Check if local is newer
        if local_path.exists():
            local_meta, _ = parse_frontmatter(local_path.read_text(encoding="utf-8", errors="replace"))
            local_updated = local_meta.get("updated", "1970-01-01")
            if local_updated >= note_data.get("updated", "1970-01-01"):
                continue
        # Write the note
        parts = ["---"]
        fm = {
            "id": note_data.get("id", note_id),
            "type": note_data.get("type", "knowledge"),
            "tier": note_data.get("tier", "core"),
            "aliases": note_data.get("aliases", []),
            "updated": note_data.get("updated", datetime.now().strftime("%Y-%m-%d")),
        }
        if note_data.get("category"):
            fm["category"] = note_data["category"]
        if note_data.get("tags"):
            fm["tags"] = note_data["tags"]
        for key, val in fm.items():
            if isinstance(val, list):
                parts.append(f"{key}: {json.dumps(val)}")
            elif isinstance(val, str) and not val.startswith('"'):
                parts.append(f'{key}: "{val}"')
            else:
                parts.append(f"{key}: {val}")
        parts.append("---")
        parts.append("")
        parts.append(note_data.get("content", ""))
        parts.append("")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_text("\n".join(parts), encoding="utf-8")
        pulled += 1
    return pulled


def hive_status(config: dict) -> dict:
    """Check hub connection and vault sync state."""
    hive_cfg = config.get("hive", {})
    hub_url = hive_cfg.get("hub_url", "")
    machine_id = hive_cfg.get("machine_id", "")
    result = {
        "connected": False,
        "hub_url": hub_url,
        "machine_id": machine_id,
        "enabled": hive_cfg.get("enabled", False),
        "replicate_tiers": hive_cfg.get("replicate_tiers", []),
        "notes_synced": 0,
    }
    if not hive_cfg.get("enabled"):
        return result
    try:
        client = HubClient(
            hub_url,
            token=hive_cfg.get("hub_token", ""),
            timeout=5,
        )
        client.connect()
        results = client.memory_search(f"vault/{machine_id}/")
        result["connected"] = True
        result["notes_synced"] = len(results) if isinstance(results, list) else 0
        client.close()
    except HubConnectionError:
        pass
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Distill Obsidian vault (tiered)")
    ap.add_argument(
        "--version",
        action="version",
        version=f"Cortex {cortex_version()}",
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument(
        "--show-config",
        action="store_true",
        help="Print resolved paths (vault, outputs, version) as JSON and exit",
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="Report release/schema versions and whether a migration is pending, then exit",
    )
    ap.add_argument(
        "--config",
        default=str(Path(__file__).parent / "cortex.yaml"),
        help="Path to config file (default: cortex.yaml next to this script)",
    )
    ap.add_argument("--hive-push", action="store_true", help="Push vault notes to hub")
    ap.add_argument("--hive-pull", action="store_true", help="Pull vault notes from hub")
    ap.add_argument("--hive-status", action="store_true", help="Show hive connection status")
    ap.add_argument(
        "--purge",
        action="store_true",
        help="Preview deletion of drained log/session notes (drained: true), then exit",
    )
    ap.add_argument(
        "--purge-apply",
        action="store_true",
        help="Delete drained log/session notes and rebuild distilled outputs",
    )
    ap.add_argument(
        "--graph",
        action="store_true",
        help="Output wiki-link graph to distilled/graph.json and print summary, then exit",
    )
    args = ap.parse_args()

    cfg_path = Path(args.config)
    cfg = load_config(cfg_path)

    if args.show_config:
        show_config(cfg, cfg_path)
        return

    # Hive commands — these don't need vault scanning
    if args.hive_status:
        status = hive_status(cfg)
        print(json.dumps(status, indent=2))
        return
    if args.hive_push:
        pushed = hive_push(cfg)
        print(f"\nHive push complete: {pushed} notes pushed to hub.")
        return
    if args.hive_pull:
        pulled = hive_pull(cfg)
        print(f"\nHive pull complete: {pulled} notes pulled from hub.")
        return

    vault = Path(cfg["vault_path"])
    if not vault.exists():
        sys.exit(f"ERROR: vault_path does not exist: {vault}")

    if args.check:
        run_check(vault)
        return

    # Purge (preview): list drained log/session notes and exit without touching
    # anything else. Apply mode deletes then falls through to a full rebuild so
    # distilled outputs + last-sync.json reflect the smaller vault.
    if args.purge and not args.purge_apply:
        purge_drained_logs(vault, apply=False)
        return
    if args.purge_apply:
        deleted = purge_drained_logs(vault, apply=True)
        if not deleted:
            return  # nothing removed — no need to rebuild
        print("\n==> Rebuilding distilled outputs after purge...")

    # Reconcile on-disk schema before doing any work (may run migrations).
    check_and_migrate(vault, args.dry_run)

    skip_dirs: set[str] = set(cfg.get("skip_dirs", ["templates"]))
    notes = scan_vault(vault, skip_dirs)
    print(f"Scanned vault: {len(notes)} notes with metadata")

    # Filter out expired notes (past expires_at date) from distillation targets.
    # Expired notes stay in the vault on disk but are excluded from core-context,
    # memory.json, and skill embeds. They still appear in the graph since they
    # exist physically.
    expired = [n for n in notes if n.is_expired()]
    if expired:
        print(f"  Skipping {len(expired)} expired note(s): {', '.join(n.name for n in expired)}")
    active_notes = [n for n in notes if not n.is_expired()]

    if args.list:
        for n in sorted(notes, key=lambda x: (x.tier, x.name)):
            print(f"  [{n.tier or 'untagged':20}] {n.name:36} type={n.note_type}")
        return

    if args.graph:
        graph = build_wiki_graph(notes)
        # Write to distilled/graph.json
        graph_out = vault / "_sync" / "distilled" / "graph.json"
        graph_data = {
            "_meta": {
                "generated": datetime.now().isoformat(),
                "source": "Cortex vault wiki-links",
                "cortex_version": cortex_version(),
                "node_count": len(graph["nodes"]),
                "edge_count": len(graph["edges"]),
                "dangling_count": len(graph["dangling"]),
                "isolated_count": len(graph["isolated"]),
                "god_node_count": len(graph["god_nodes"]),
            },
            **graph,
        }
        graph_out.parent.mkdir(parents=True, exist_ok=True)
        graph_out.write_text(json.dumps(graph_data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote graph: {graph_out}")
        print(f"  Nodes: {len(graph['nodes'])}")
        print(f"  Edges: {len(graph['edges'])}")
        print(f"  Dangling links: {len(graph['dangling'])}")
        print(f"  Isolated nodes: {len(graph['isolated'])}")
        if graph["isolated"]:
            print(f"    {', '.join(graph['isolated'][:10])}")
        print(f"  God nodes (degree > threshold): {len(graph['god_nodes'])}")
        for g in graph["god_nodes"][:5]:
            print(f"    {g['id']}: degree {g['degree']}")
        return

    eager_tiers: list[str] = cfg.get("eager_tiers", ["core"])
    exclude_tags: list[str] = cfg.get("exclude_tags", [])
    vault_only_types: list[str] = cfg.get("vault_only_types", [])
    strip_links: bool = cfg.get("strip_wiki_links", True)
    targets: dict = cfg.get("targets", {})

    dry = args.dry_run

    core_out: Path | None = None
    cc = targets.get("core_context", {})
    if cc.get("enabled"):
        core_out = sync_core_context(active_notes, cc, eager_tiers, strip_links, dry)

    sk = targets.get("skills", {})
    if sk.get("enabled"):
        sync_skill_embeds(active_notes, sk, strip_links, dry)

    pr = targets.get("projects", {})
    if pr.get("enabled"):
        sync_projects(active_notes, pr, strip_links, dry)

    pa = targets.get("python-agents", {})
    if pa.get("enabled"):
        sync_python_agents(active_notes, pa, exclude_tags, vault_only_types, dry)

    if core_out:
        # prune_legacy is opt-in — off by default to prevent accidental deletions
        if cc.get("prune_legacy", False):
            prune_distilled_opencode(core_out, dry)
        if cc.get("opencode_config"):
            update_opencode_instructions(Path(cc["opencode_config"]), core_out, dry)

    if not dry:
        save_sync_state(vault, notes)
        print(f"\nSync complete. {len(notes)} notes processed.")
    else:
        print("\n[DRY RUN] No files were modified.")


if __name__ == "__main__":
    main()

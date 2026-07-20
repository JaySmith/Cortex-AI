#!/usr/bin/env python3
"""
gen-portfolio.py — Generate a phase-grouped portfolio from Cortex project notes.

Scans <projects_dir>/**/*.md for notes with `tier: project`, groups them by
`phase` (discovery | delivery | completed), and writes a PORTFOLIO.md with
each project's goals and roadmap.

Optionally enriches each project with LIVE Jira status by reading the note's
`jira_epic` frontmatter and fetching from the Jira REST API.

Usage:
  python3 gen-portfolio.py --jira-base https://company.atlassian.net
  python3 gen-portfolio.py --no-jira
  python3 gen-portfolio.py --jira-base https://company.atlassian.net --vault /path/to/vault
  python3 gen-portfolio.py --no-jira --skip-ids old-index,scratch

Output: <vault>/PORTFOLIO.md  (or --output to override)
"""

# --- venv bootstrap -------------------------------------------------------
# gen-portfolio.py requires PyYAML which lives in the sibling .venv, not system
# Python (macOS Homebrew Python is externally-managed and can't have packages
# installed into it). If we're not already running inside that venv, re-exec
# ourselves with its interpreter. os.execv replaces the current process image
# outright — no subprocess overhead, and the exact-path check guards against
# an infinite loop. If no venv exists we fall through and let the yaml
# ImportError below fire naturally. Cross-platform: Windows uses
# .venv/Scripts/python.exe, POSIX uses .venv/bin/python.
import os as _os
import sys as _sys
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

import argparse
import base64
import json
import os
import re
import ssl
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("ERROR: PyYAML required. Run: pip install -r requirements.txt")


# ---------------------------------------------------------------------------
# Vault path detection
# ---------------------------------------------------------------------------


def get_vault_path() -> Path:
    """Return vault path from env or infer from script location (<vault>/_sync/)."""
    if env_vault := os.environ.get("CORTEX_VAULT"):
        return Path(env_vault)
    # Assume this script lives in <vault>/_sync/
    return Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Frontmatter + section parsing
# ---------------------------------------------------------------------------


def parse_note(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    meta: dict = {}
    body: str = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            try:
                meta = yaml.safe_load(text[3:end]) or {}
            except yaml.YAMLError:
                meta = {}
            body = text[end + 4 :]
    return meta, body


def extract_section(body: str, heading: str) -> str:
    """Return the markdown under a `## heading` up to the next `## `."""
    pat = re.compile(rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s|\Z)", re.M | re.S)
    m = pat.search(body)
    if not m:
        return ""
    out = re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S)
    return out.strip()


def title_of(meta: dict, path: Path) -> str:
    al = meta.get("aliases") or []
    if isinstance(al, list) and al:
        return str(al[0])
    return (meta.get("id") or path.stem).replace("-", " ").title()


# ---------------------------------------------------------------------------
# Jira
# ---------------------------------------------------------------------------


def jira_creds() -> tuple[str | None, str | None]:
    """Try to read Jira credentials from ~/.claude/.mcp.json."""
    p = Path.home() / ".claude" / ".mcp.json"
    try:
        d = json.loads(p.read_text())
        env = d["mcpServers"]["atlassian"]["env"]
        return env["JIRA_USERNAME"], env["JIRA_API_TOKEN"]
    except Exception as e:
        print(f"  (Jira creds unavailable: {e}) — skipping live status")
        return None, None


def jira_status(key: str, jira_base: str, user: str, token: str) -> str:
    """Fetch issue status from Jira REST API."""
    url = f"{jira_base}/rest/api/3/issue/{urllib.parse.quote(key)}?fields=status,summary"
    cred = base64.b64encode(f"{user}:{token}".encode()).decode()
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Basic {cred}", "Accept": "application/json"},
    )
    # Use the system default SSL context (validates certificates properly)
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
            d = json.loads(r.read())
        return d.get("fields", {}).get("status", {}).get("name", "?")
    except Exception as e:
        return f"(lookup failed: {type(e).__name__})"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Generate a phase-grouped portfolio from Cortex project notes"
    )
    ap.add_argument("--no-jira", action="store_true", help="skip live Jira status lookups")
    ap.add_argument(
        "--jira-base",
        help="Jira base URL, e.g. https://company.atlassian.net (required unless --no-jira)",
    )
    ap.add_argument(
        "--vault", help="Vault root path (auto-detected if this script is in <vault>/_sync/)"
    )
    ap.add_argument(
        "--projects-dir",
        default="entities/projects",
        help="Projects directory relative to vault root (default: entities/projects)",
    )
    ap.add_argument(
        "--output",
        default="PORTFOLIO.md",
        help="Output filename relative to vault root (default: PORTFOLIO.md)",
    )
    ap.add_argument(
        "--skip-ids",
        default="",
        help="Comma-separated note IDs to skip (e.g. index or roll-up notes)",
    )
    args = ap.parse_args()

    # Validate: --jira-base is required unless --no-jira
    if not args.no_jira and not args.jira_base:
        sys.exit(
            "ERROR: --jira-base is required when fetching live Jira status.\n"
            "       Pass --jira-base https://yourcompany.atlassian.net\n"
            "       or use --no-jira to skip live status lookups."
        )

    vault = Path(args.vault) if args.vault else get_vault_path()
    projects_dir = vault / args.projects_dir
    out = vault / args.output
    skip_ids: set[str] = {s.strip() for s in args.skip_ids.split(",") if s.strip()}

    if not projects_dir.exists():
        sys.exit(f"ERROR: projects directory not found: {projects_dir}")

    projects: list[dict] = []
    for md in projects_dir.rglob("*.md"):
        meta, body = parse_note(md)
        if meta.get("tier") != "project":
            continue
        note_id = meta.get("id") or md.stem
        if note_id in skip_ids:
            continue
        projects.append(
            {
                "path": md,
                "title": title_of(meta, md),
                "phase": (meta.get("phase") or "unphased").lower(),
                "jira_epic": (meta.get("jira_epic") or "").strip(),
                "personal": bool(meta.get("personal")),
                "goals": extract_section(body, "Goals"),
                "roadmap": extract_section(body, "Roadmap"),
            }
        )

    user = token = None
    if not args.no_jira:
        user, token = jira_creds()
    use_jira = bool(user and token and args.jira_base)

    # Live status lookups — sequential with per-call timeout.
    #
    # For parallel fetches (faster with many projects), replace the loop below with:
    #
    # from concurrent.futures import ThreadPoolExecutor, as_completed
    # with ThreadPoolExecutor(max_workers=5) as ex:
    #     futures = {
    #         ex.submit(jira_status, p["jira_epic"], args.jira_base, user, token): p
    #         for p in projects if p["jira_epic"]
    #     }
    #     for future in as_completed(futures):
    #         futures[future]["status"] = future.result()
    #
    for p in projects:
        p["status"] = ""
        if use_jira and p["jira_epic"]:
            assert user is not None and token is not None  # narrowed by use_jira check above
            p["status"] = jira_status(p["jira_epic"], args.jira_base, user, token)

    phases = ["discovery", "delivery", "completed"]
    by_phase: dict[str, list[dict]] = {ph: [] for ph in phases}
    by_phase.setdefault("unphased", [])
    for p in sorted(projects, key=lambda x: x["title"].lower()):
        by_phase.setdefault(p["phase"], []).append(p)

    lines: list[str] = [
        "# Portfolio — Projects by Phase",
        "",
        f"_Auto-generated by `gen-portfolio.py` on {datetime.now():%Y-%m-%d %H:%M}."
        f"{' Live Jira status included.' if use_jira else ' Vault data only.'} Do not edit by hand._",
        "",
        "**Discovery** = reviewing, defining, shaping the solution.",
        "**Delivery** = actively building and delivering the defined value.",
        "",
    ]

    def phase_block(name: str, items: list[dict], blurb: str) -> None:
        lines.append(f"## {name} ({len(items)})")
        lines.append("")
        lines.append(blurb)
        lines.append("")
        if not items:
            lines.append("_No projects in this phase._")
            lines.append("")
            return
        # Summary table
        lines.append("| Project | Jira | Live Status |")
        lines.append("|---------|------|-------------|")
        for p in items:
            epic = f"`{p['jira_epic']}`" if p["jira_epic"] else "—"
            st = p["status"] or ("—" if not p["jira_epic"] else "(no jira)")
            tag = " _(personal)_" if p["personal"] else ""
            lines.append(f"| {p['title']}{tag} | {epic} | {st} |")
        lines.append("")
        # Detail per project
        for p in items:
            lines.append(f"### {p['title']}")
            if p["jira_epic"] and args.jira_base:
                live = f" — live: **{p['status']}**" if p["status"] else ""
                lines.append(
                    f"_Jira: [{p['jira_epic']}]({args.jira_base}/browse/{p['jira_epic']}){live}_"
                )
            lines.append("")
            lines.append("**Goals**")
            lines.append("")
            lines.append(p["goals"] or "_(none recorded)_")
            lines.append("")
            lines.append("**Roadmap**")
            lines.append("")
            lines.append(p["roadmap"] or "_(none recorded)_")
            lines.append("")

    phase_block(
        "Discovery",
        by_phase.get("discovery", []),
        "Reviewing, defining, and proving solution + value before committing to build.",
    )
    phase_block(
        "Delivery",
        by_phase.get("delivery", []),
        "Actively building and shipping the value defined in Discovery.",
    )
    phase_block(
        "Completed",
        by_phase.get("completed", []),
        "Delivered/closed projects.",
    )

    extra = by_phase.get("unphased", [])
    if extra:
        phase_block(
            "Unphased", extra, "Projects missing a `phase` frontmatter field — classify them."
        )

    out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(
        f"Wrote {out} — {len(projects)} projects "
        f"({len(by_phase.get('discovery', []))} discovery, "
        f"{len(by_phase.get('delivery', []))} delivery, "
        f"{len(by_phase.get('completed', []))} completed"
        f"{', ' + str(len(extra)) + ' unphased' if extra else ''})."
    )


if __name__ == "__main__":
    main()

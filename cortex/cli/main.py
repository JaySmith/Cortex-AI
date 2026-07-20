#! /usr/bin/env python3
"""
cortex.cli.main — Typer CLI entry point for the `cortex` command.

All user-facing operations consolidated behind a single CLI:
  cortex bootstrap       Create venv + install Python deps
  cortex install         Bootstrap or upgrade Cortex for a user
  cortex install --upgrade Upgrade an existing install
  cortex uninstall       Revert Cortex-installed assets
  cortex distill         Run vault-to-agent distillation
  cortex status          Show basic health of Cortex
  cortex memory search   Search distilled memory
  cortex memory write    Write a memory note (metadata-only in Phase 1)
  cortex import          Import existing agent context
  cortex version         Print version information
"""

from __future__ import annotations

import os
import re
import sys
import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer

from cortex import __version__
from cortex.cli.commands import import_agent as import_agent_module
from cortex.cli.commands import uninstall as uninstall_cmd
from cortex.distiller.core import (
    cortex_version,
    schema_version,
    run_distill,
    load_config,
    read_vault_schema,
)

app = typer.Typer(
    name="cortex",
    help="Persistent, tiered memory for AI coding agents",
    no_args_is_help=True,
)
memory_app = typer.Typer(
    name="memory",
    help="Search and write vault memory",
    no_args_is_help=True,
)
app.add_typer(memory_app, name="memory")


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _find_vault() -> Path:
    """Try to find an existing vault from common locations."""
    candidates = [
        Path.cwd(),
        Path.home() / "Cortex",
    ]
    for p in candidates:
        sync_cfg = p / "_sync" / "cortex.yaml"
        if sync_cfg.exists():
            return p
    return Path.cwd()


def _backup_file(src: Path, backup_dir: Path) -> Path | None:
    """Snapshot a file into backup_dir. Returns the backup path, or None if
    the source didn't exist."""
    if not src.exists():
        return None
    flat = str(src).replace(str(Path.home()), "~").replace("/", "_").lstrip("_")
    dst = backup_dir / flat
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def _record_action(actions_file: Path, op: str, path: str, saved_as: str = "") -> None:
    entry = {"op": op, "path": path}
    if saved_as:
        entry["saved_as"] = saved_as
    with open(actions_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _write_manifest(
    manifest_path: Path,
    actions_file: Path,
    vault_root: str,
    repo_root: str,
) -> None:
    actions = []
    if actions_file.exists():
        for line in actions_file.read_text().splitlines():
            line = line.strip()
            if line:
                actions.append(json.loads(line))
        actions_file.unlink()
    if not actions:
        manifest_path.parent.rmdir() if not any(manifest_path.parent.iterdir()) else None
        return
    doc = {
        "cortex_version": cortex_version(),
        "schema_version": schema_version(),
        "created": datetime.now().isoformat(),
        "vault_root": vault_root,
        "repo_root": repo_root,
        "actions": actions,
    }
    manifest_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# bootstrap
# ---------------------------------------------------------------------------


@app.command()
def bootstrap(
    repo_root: Optional[str] = typer.Argument(
        None,
        help="Repo root (default: auto-detect)",
    ),
) -> None:
    """Create a venv and install Python dependencies.

    This is the chicken-and-egg command: run it before `cortex install` if you
    don't have a venv yet. Safe to re-run (idempotent).
    """
    root = Path(repo_root) if repo_root else _REPO_ROOT
    venv_dir = root / ".venv"

    typer.echo("==> Cortex bootstrap")
    typer.echo(f"    repo: {root}")

    # Check python3
    if not shutil.which("python3"):
        typer.echo("ERROR: python3 not found on PATH.", err=True)
        raise typer.Exit(code=1)

    # Create venv
    if not venv_dir.exists():
        typer.echo("    creating venv ...")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
    else:
        typer.echo("    venv already exists")

    python = venv_dir / "bin" / "python"

    # Upgrade pip
    typer.echo("    upgrading pip ...")
    subprocess.run(
        [str(python), "-m", "pip", "install", "--quiet", "--upgrade", "pip"],
        check=True,
    )

    # Install deps
    req = root / "requirements.txt"
    if req.exists():
        typer.echo("    installing dependencies ...")
        subprocess.run(
            [str(python), "-m", "pip", "install", "--quiet", "-r", str(req)],
            check=True,
        )
    else:
        typer.echo("    installing package ...")
        subprocess.run(
            [str(python), "-m", "pip", "install", "--quiet", "-e", str(root)],
            check=True,
        )

    typer.echo(f"\nBootstrap complete. Activate with:")
    typer.echo(f"  source {venv_dir}/bin/activate")
    typer.echo(f"  cortex install")


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------

# Files the distiller needs in vault/_sync/
_DISTILLER_FILES = [
    "distill.py",
    "hive_client.py",
    "cortex-import.py",
    "cortex-uninstall.py",
    "gen-portfolio.py",
    "VERSION",
    "SCHEMA_VERSION",
    "CHANGELOG.md",
]


@app.command()
def install(
    vault: Optional[str] = typer.Argument(
        None,
        help="Vault path (default: auto-detect or prompt)",
    ),
    upgrade: bool = typer.Option(
        False,
        "--upgrade",
        help="Upgrade an existing install",
    ),
    no_distill: bool = typer.Option(
        False,
        "--no-distill",
        help="Skip re-distillation after install/upgrade",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would change without writing anything",
    ),
) -> None:
    """Bootstrap or upgrade Cortex for a user.

    Handles everything: venv deps, config generation, distiller deployment,
    skill installation, backup, and distillation. Replaces setup.sh and
    deploy.sh.
    """
    repo_root = _REPO_ROOT

    if not vault:
        vault = typer.prompt(
            "Vault path", default=str(_find_vault())
        )
    vault_path = Path(vault).expanduser()

    if not vault_path.exists():
        typer.echo(f"ERROR: vault path does not exist: {vault_path}", err=True)
        raise typer.Exit(code=1)

    vault_path = vault_path.resolve()
    sync_dir = vault_path / "_sync"
    distilled_dir = sync_dir / "distilled"
    skills_dir = distilled_dir / "skills"
    memory_json = distilled_dir / "memory.json"
    core_context = distilled_dir / "opencode" / "core-context.md"
    projects_dir = distilled_dir / "opencode" / "projects"
    config_file = sync_dir / "cortex.yaml"
    opencode_skills_dir = Path.home() / ".config" / "opencode" / "skills"

    # Install manifest — records everything this run creates/modifies so
    # `cortex uninstall` can cleanly revert.
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    manifest_dir = sync_dir / "backups" / f"{stamp}-{'upgrade' if upgrade else 'install'}"
    actions_file = manifest_dir / ".actions.jsonl"
    if not dry_run:
        manifest_dir.mkdir(parents=True, exist_ok=True)
        actions_file.write_text("")

    rel_ver = cortex_version()
    schema_ver = schema_version()
    mode = "DRY-RUN" if dry_run else "APPLY"
    typer.echo(f"==> Cortex {'upgrade' if upgrade else 'install'} [{mode}] (v{rel_ver}, schema v{schema_ver})")
    typer.echo(f"    vault: {vault_path}")

    # ---- Version guard (upgrade only) ----
    if upgrade:
        live_schema = read_vault_schema(vault_path)
        if live_schema is not None and live_schema > schema_ver:
            typer.echo(
                f"ERROR: live vault schema (v{live_schema}) is NEWER than this "
                f"code (v{schema_ver}). Refusing to downgrade.",
                err=True,
            )
            raise typer.Exit(code=1)

    python = sys.executable

    # ---- [1/5] Ensure venv deps ----
    typer.echo("\n==> [1/5] Dependencies")
    venv_dir = repo_root / ".venv"
    venv_python = venv_dir / "bin" / "python"
    if venv_python.exists():
        typer.echo("    venv deps already installed")
    elif not dry_run:
        typer.echo("    venv not found — run 'cortex bootstrap' first, or")
        typer.echo("    installing deps inline ...")
        subprocess.run([python, "-m", "venv", str(venv_dir)], check=True)
        subprocess.run(
            [str(venv_python), "-m", "pip", "install", "--quiet", "--upgrade", "pip"],
            check=True,
        )
        req = repo_root / "requirements.txt"
        if req.exists():
            subprocess.run(
                [str(venv_python), "-m", "pip", "install", "--quiet", "-r", str(req)],
                check=True,
            )
        typer.echo("    deps installed into .venv")
    else:
        typer.echo("    [DRY] would create venv and install deps")

    # ---- [2/5] Deploy distiller ----
    typer.echo("\n==> [2/5] Distiller")
    if upgrade:
        # Backup existing distiller files before overwriting
        if not dry_run:
            for fname in _DISTILLER_FILES:
                src = sync_dir / fname
                _backup_file(src, manifest_dir)
        typer.echo(f"    deploying distiller -> {sync_dir}")
    else:
        typer.echo(f"    distiller -> {sync_dir}")

    if not dry_run:
        for fname in _DISTILLER_FILES:
            src = repo_root / fname
            if src.exists():
                dst = sync_dir / fname
                shutil.copy2(src, dst)
                _record_action(actions_file, "created", str(dst))

    # ---- [3/5] Config (only if missing) ----
    typer.echo("\n==> [3/5] Config")
    sync_dir.mkdir(parents=True, exist_ok=True)
    if config_file.exists():
        typer.echo(f"    {config_file} already exists — leaving it untouched")
    else:
        yaml_content = (
            f"# Cortex — generated by cortex install\n"
            f"# Points at: {vault_path}\n"
            f"schema_version: {schema_ver}\n"
            f'vault_path: "{vault_path}"\n'
            f"\n"
            f"eager_tiers:\n"
            f"  - core\n"
            f"\n"
            f"skip_dirs:\n"
            f"  - templates\n"
            f"  - archive\n"
            f"\n"
            f"exclude_tags:\n"
            f"  - draft\n"
            f"  - archived\n"
            f"\n"
            f"vault_only_types:\n"
            f"  - session\n"
            f"  - log\n"
            f"\n"
            f"targets:\n"
            f"  core_context:\n"
            f"    enabled: true\n"
            f"    type: core-context\n"
            f'    output_file: "{core_context}"\n'
            f"\n"
            f"  skills:\n"
            f"    enabled: true\n"
            f"    type: skill-embed\n"
            f'    skills_dir: "{skills_dir}"\n'
            f'    embed_filename: "reference.md"\n'
            f"\n"
            f"  projects:\n"
            f"    enabled: true\n"
            f"    type: project-context\n"
            f'    output_dir: "{projects_dir}"\n'
            f"\n"
            f"  python-agents:\n"
            f"    enabled: true\n"
            f"    type: json\n"
            f'    output_file: "{memory_json}"\n'
            f"    include_types:\n"
            f"      - knowledge\n"
            f"      - entity\n"
            f"\n"
            f"strip_wiki_links: true\n"
        )
        if dry_run:
            typer.echo(f"    [DRY] would create {config_file}")
        else:
            config_file.write_text(yaml_content, encoding="utf-8")
            _record_action(actions_file, "created", str(config_file))
            typer.echo(f"    wrote {config_file}")

    # ---- [4/5] Skill + first distill ----
    typer.echo("\n==> [4/5] Skill + distill")
    if not dry_run:
        # Pre-create skill dirs
        for md in vault_path.rglob("*.md"):
            if any(p.startswith((".", "_")) for p in md.relative_to(vault_path).parts):
                continue
            try:
                text = md.read_text(encoding="utf-8")
            except Exception:
                continue
            m = re.search(r"^tier:\s*skill:(\S+)", text, re.M)
            if m:
                (skills_dir / m.group(1)).mkdir(parents=True, exist_ok=True)

    # Install skill
    skill_src = repo_root / "skills" / "cortex-ai" / "SKILL.md"
    if skill_src.exists():
        skill_dest_dir = opencode_skills_dir / "cortex-ai"
        skill_dest = skill_dest_dir / "SKILL.md"
        if dry_run:
            typer.echo(f"    [DRY] would install skill -> {skill_dest}")
        else:
            # Backup existing skill
            if skill_dest.exists():
                _backup_file(skill_dest, manifest_dir)
                _record_action(actions_file, "modified", str(skill_dest),
                               f"cortex-ai.SKILL.md.bak")
            else:
                _record_action(actions_file, "created", str(skill_dest))
            skill_dest_dir.mkdir(parents=True, exist_ok=True)
            text = skill_src.read_text(encoding="utf-8")
            text = text.replace("<CORTEX_HOME>", str(repo_root))
            skill_dest.write_text(text, encoding="utf-8")
            typer.echo(f"    installed skill -> {skill_dest}")
    else:
        typer.echo(
            f"    WARNING: skill source not found at {skill_src} — skipping",
            err=True,
        )

    # Run distill
    if not dry_run and config_file.exists():
        rc = run_distill(config_path=config_file)
        if rc != 0:
            typer.echo("    WARNING: distill had errors", err=True)

    # ---- [5/5] Re-distill if upgrade ----
    if upgrade and not no_distill and not dry_run:
        typer.echo("\n==> [5/5] Re-distill")
        rc = run_distill(config_path=config_file)
        if rc != 0:
            typer.echo("    WARNING: re-distill had errors", err=True)
        typer.echo("    Re-distilled after upgrade")
    elif not upgrade:
        typer.echo("\n==> [5/5] (skipped — initial install)")

    # ---- Write manifest ----
    if not dry_run:
        _write_manifest(manifest_dir / "manifest.json", actions_file,
                        str(vault_path), str(repo_root))
        # Clean up empty backup dir
        if manifest_dir.exists() and not any(
            f for f in manifest_dir.iterdir() if f.name != ".actions.jsonl"
        ):
            actions_file.unlink(missing_ok=True)
            manifest_dir.rmdir()

    # ---- Done ----
    typer.echo("\n==> Done")
    if upgrade:
        typer.echo("Upgrade complete. Restart your agent to load changes.")
    else:
        typer.echo("\nCortex is installed. Next steps:")
        typer.echo(f"  cortex status         # verify the install")
        typer.echo(f"  cortex version        # show version info")
        typer.echo(f"  cortex import --dry-run  # import existing agent context")
        typer.echo(f"  cortex distill        # run distillation manually")


# ---------------------------------------------------------------------------
# uninstall
# ---------------------------------------------------------------------------


@app.command()
def uninstall(
    vault: str = typer.Option(
        ...,
        "--vault",
        help="Vault root Cortex was installed against",
        prompt=True,
    ),
    latest: bool = typer.Option(
        True,
        "--latest",
        help="Undo only the most recent manifest",
    ),
    backup: Optional[str] = typer.Option(
        None,
        "--backup",
        help="Undo a specific backup dir name",
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Actually make changes (default is dry-run)",
    ),
    purge: bool = typer.Option(
        False,
        "--purge",
        help="Also delete _sync/distilled (notes are kept)",
    ),
) -> None:
    """Safely revert Cortex-installed assets while preserving user notes."""
    vault_path = Path(vault).expanduser()
    rc = uninstall_cmd.run_uninstall(
        vault=vault_path,
        latest=latest if not backup else False,
        backup=backup,
        apply=apply,
        purge=purge,
    )
    raise typer.Exit(code=rc)


# ---------------------------------------------------------------------------
# distill
# ---------------------------------------------------------------------------


@app.command()
def distill(
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show changes without writing"
    ),
    list_notes: bool = typer.Option(
        False, "--list", help="List all vault notes with tier/type"
    ),
    show_config: bool = typer.Option(
        False, "--show-config", help="Print resolved paths as JSON"
    ),
    check: bool = typer.Option(
        False, "--check", help="Report version/schema health and exit"
    ),
    graph: bool = typer.Option(
        False, "--graph", help="Output wiki-link graph and exit"
    ),
    purge: bool = typer.Option(
        False,
        "--purge",
        help="Preview deletion of drained log/session notes",
    ),
    purge_apply: bool = typer.Option(
        False,
        "--purge-apply",
        help="Delete drained log/session notes and rebuild",
    ),
    hive_push: bool = typer.Option(
        False, "--hive-push", help="Push vault notes to hub"
    ),
    hive_pull: bool = typer.Option(
        False, "--hive-pull", help="Pull vault notes from hub"
    ),
    hive_status: bool = typer.Option(
        False, "--hive-status", help="Show hive connection status"
    ),
    config_path: Optional[str] = typer.Option(
        None,
        "--config",
        help="Path to cortex.yaml config file",
    ),
) -> None:
    """Run the vault-to-agent distillation process."""
    cfg_path = (
        Path(config_path)
        if config_path
        else Path.cwd() / "_sync" / "cortex.yaml"
    )
    rc = run_distill(
        config_path=cfg_path,
        dry_run=dry_run,
        list_only=list_notes,
        show_config_only=show_config,
        check_only=check,
        graph_only=graph,
        purge_only=purge,
        purge_apply=purge_apply,
        hive_push_only=hive_push,
        hive_pull_only=hive_pull,
        hive_status_only=hive_status,
    )
    raise typer.Exit(code=rc)


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@app.command()
def status(
    vault: Optional[str] = typer.Option(
        None,
        "--vault",
        help="Vault path (default: auto-detect from config discovery)",
    ),
) -> None:
    """Show basic health of the Cortex installation."""
    # Try to find config
    config_file = None
    vault_path = None
    if vault:
        vault_path = Path(vault).expanduser()
        cfg = vault_path / "_sync" / "cortex.yaml"
        if cfg.exists():
            config_file = cfg
    else:
        # Search common locations
        for p in [Path.cwd(), Path.home() / "Cortex"]:
            cfg = p / "_sync" / "cortex.yaml"
            if cfg.exists():
                config_file = cfg
                vault_path = p
                break

    if config_file and config_file.exists():
        typer.echo("Config:           found")
        typer.echo(f"  path: {config_file}")
        try:
            cfg_data = load_config(config_file)
            vp = Path(cfg_data.get("vault_path", ""))
            typer.echo(f"  vault: {vp}")
            if vp.exists():
                typer.echo("Vault:            found")
            else:
                typer.echo("Vault:            MISSING")
            mem_json = vp / "_sync" / "distilled" / "memory.json"
            if mem_json.exists():
                typer.echo("Distilled memory: found")
                schema = read_vault_schema(vp)
                code_schema = schema_version()
                if schema is None:
                    typer.echo("Schema:           unknown (fresh vault?)")
                elif schema == code_schema:
                    typer.echo("Schema:           compatible")
                elif schema < code_schema:
                    typer.echo(
                        f"Schema:           migration pending "
                        f"(v{schema} -> v{code_schema})"
                    )
                else:
                    typer.echo(
                        f"Schema:           ERROR — vault newer than code",
                        err=True,
                    )
            else:
                typer.echo("Distilled memory: MISSING — run 'cortex distill'")

            # Check opencode config exists
            opencode_cfg = (
                Path.home() / ".config" / "opencode" / "opencode.jsonc"
            )
            if not opencode_cfg.exists():
                opencode_cfg = (
                    Path.home() / ".config" / "opencode" / "opencode.json"
                )
            env_cfg = os.environ.get("OPENCODE_CONFIG")
            if env_cfg:
                opencode_cfg = Path(env_cfg)
            if opencode_cfg.exists():
                typer.echo("opencode config:  found")
            else:
                typer.echo("opencode config:  not found")

            typer.echo("\nStatus:           HEALTHY" if vp.exists() and mem_json.exists()
                       else "\nStatus:           NEEDS ATTENTION")
        except Exception as e:
            typer.echo(f"ERROR reading config: {e}", err=True)
            raise typer.Exit(code=1)
    else:
        typer.echo("Config:           not found")
        typer.echo("\nCortex is not installed in this environment.")
        typer.echo("Run 'cortex install' to get started.")
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# import
# ---------------------------------------------------------------------------


@app.command(name="import")
def import_cmd(
    vault: Optional[str] = typer.Option(
        None,
        "--vault",
        help="Vault root to import into (default: auto-detect)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would happen without writing anything",
    ),
    agents_md: Optional[str] = typer.Option(
        None, "--agents-md", help="Path to AGENTS.md"
    ),
    claude_md: Optional[str] = typer.Option(
        None, "--claude-md", help="Path to CLAUDE.md"
    ),
    opencode: Optional[str] = typer.Option(
        None, "--opencode", help="Path to opencode.jsonc"
    ),
    claude_memory: Optional[str] = typer.Option(
        None,
        "--claude-memory",
        help="Path to ~/.claude/memory directory",
    ),
) -> None:
    """Import existing agent context into the Cortex vault."""
    # Auto-detect vault if not provided
    if not vault:
        for p in [Path.cwd(), Path.home() / "Cortex"]:
            cfg = p / "_sync" / "cortex.yaml"
            if cfg.exists():
                vault = str(p)
                break
        if not vault:
            vault = str(Path.cwd())

    vault_path = Path(vault).expanduser()
    import_agent_module.run_import(
        vault=vault_path,
        dry_run=dry_run,
        agents_md=agents_md,
        claude_md=claude_md,
        opencode=opencode,
        claude_memory=claude_memory,
    )


# ---------------------------------------------------------------------------
# version
# ---------------------------------------------------------------------------


@app.command()
def version() -> None:
    """Print Cortex version information."""
    typer.echo(f"Cortex:  {cortex_version()}")
    typer.echo(f"Schema:  {schema_version()}")


# ---------------------------------------------------------------------------
# memory subcommands
# ---------------------------------------------------------------------------


@memory_app.command()
def search(
    query: str = typer.Argument(
        ..., help="Search query string"
    ),
    vault: Optional[str] = typer.Option(
        None, "--vault", help="Vault path (auto-detect by default)"
    ),
) -> None:
    """Search distilled memory from the CLI."""
    # Find memory.json
    mem_path = None
    if vault:
        vp = Path(vault).expanduser()
        mem_path = vp / "_sync" / "distilled" / "memory.json"
    else:
        for p in [Path.cwd(), Path.home() / "Cortex"]:
            mp = p / "_sync" / "distilled" / "memory.json"
            if mp.exists():
                mem_path = mp
                break

    if not mem_path or not mem_path.exists():
        typer.echo("ERROR: memory.json not found. Run 'cortex distill' first.", err=True)
        raise typer.Exit(code=1)

    try:
        data = json.loads(mem_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        typer.echo(f"ERROR: could not read memory.json: {e}", err=True)
        raise typer.Exit(code=1)

    notes = data.get("notes", {})
    query_lower = query.lower()
    results = []
    for nid, note in notes.items():
        score = 0
        if query_lower in nid:
            score += 10
        for alias in note.get("aliases", []):
            if query_lower in alias.lower():
                score += 8
        for tag in note.get("tags", []):
            if query_lower == tag.lower():
                score += 6
            elif query_lower in tag.lower():
                score += 3
        if query_lower in note.get("category", "").lower():
            score += 5
        if query_lower in note.get("content", "").lower():
            score += 1
        if score > 0:
            results.append((score, nid, note))

    results.sort(key=lambda x: -x[0])

    if not results:
        typer.echo(f"No results for '{query}'")
        return

    typer.echo(f"Found {len(results)} result(s) for '{query}':\n")
    for score, nid, note in results[:20]:
        alias = note.get("aliases", [""])[0]
        cat = note.get("category", "")
        snippet = note.get("content", "")[:80].replace("\n", " ")
        typer.echo(
            f"  {nid}  "
            f"· {note.get('type', '?')}/{cat}  "
            f"· {alias}"
        )
        if snippet:
            typer.echo(f"    {snippet}...")


@memory_app.command()
def write(
    title: str = typer.Option(
        ..., "--title", help="Note title (becomes alias and id)"
    ),
    note_type: str = typer.Option(
        ..., "--type", help="Note type (knowledge, entity, feedback, etc.)"
    ),
    tier: str = typer.Option(
        ..., "--tier", help="Tier (core, skill:<name>, project, vault-only)"
    ),
    tags: Optional[str] = typer.Option(
        None, "--tags", help="Comma-separated tags"
    ),
    category: Optional[str] = typer.Option(
        None, "--category", help="Category (patterns, api, projects, etc.)"
    ),
    vault: Optional[str] = typer.Option(
        None, "--vault", help="Vault path (auto-detect by default)"
    ),
) -> None:
    """Write a metadata-only memory note to the vault."""
    # Find vault
    vault_path = None
    if vault:
        vault_path = Path(vault).expanduser()
    else:
        for p in [Path.cwd(), Path.home() / "Cortex"]:
            cfg = p / "_sync" / "cortex.yaml"
            if cfg.exists():
                vault_path = p
                break

    if not vault_path or not vault_path.exists():
        typer.echo("ERROR: vault not found. Run 'cortex install' first.", err=True)
        raise typer.Exit(code=1)

    note_id = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if not note_id:
        note_id = "untitled"

    today = datetime.now().strftime("%Y-%m-%d")

    tag_list = (
        [t.strip() for t in tags.split(",") if t.strip()]
        if tags
        else []
    )

    # Determine type directory
    type_dir_name = note_type + ("s" if not note_type.endswith("s") else "")
    target_dir = vault_path / type_dir_name
    target_dir.mkdir(parents=True, exist_ok=True)

    note_path = target_dir / f"{note_id}.md"
    if note_path.exists():
        typer.echo(f"ERROR: note already exists at {note_path}", err=True)
        raise typer.Exit(code=1)

    parts = [
        "---",
        f"id: {note_id}",
        f"type: {note_type}",
        f'tier: "{tier}"',
        f'aliases: ["{title}"]',
        f'updated: "{today}"',
    ]
    if category:
        parts.append(f'category: "{category}"')
    if tag_list:
        parts.append(f"tags: [{', '.join(tag_list)}]")
    parts.append("---")
    parts.append("")
    parts.append("")

    content = "\n".join(parts)
    note_path.write_text(content, encoding="utf-8")
    typer.echo(f"Created note: {note_path}")
    typer.echo(f"  id: {note_id}")
    typer.echo(f"  type: {note_type}  tier: {tier}")
    if tag_list:
        typer.echo(f"  tags: {tag_list}")
    typer.echo("\nRun 'cortex distill' to rebuild distilled output.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    app()


if __name__ == "__main__":
    main()

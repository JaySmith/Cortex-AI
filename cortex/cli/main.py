#! /usr/bin/env python3
"""
cortex.cli.main — Typer CLI entry point for the `cortex` command.

All user-facing operations consolidated behind a single CLI:
  cortex bootstrap       Create venv + install Python deps
  cortex install         Bootstrap or upgrade Cortex for a user
  cortex install --upgrade Upgrade an existing install
  cortex uninstall       Revert Cortex-installed assets
  cortex encode          Run vault-to-agent encoding
  cortex status          Show basic health of Cortex
   cortex memory search   Search encoded memory
   cortex memory get      Fetch a single note by id
   cortex memory write    Write a memory note to the vault
  cortex import          Import existing agent context
  cortex version         Print version information
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import typer

from cortex.cli.commands import import_agent as import_agent_module
from cortex.cli.commands import uninstall as uninstall_cmd
from cortex.encoder.core import (
    cortex_version,
    load_config,
    read_vault_schema,
    run_encode,
    schema_version,
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

# Platform subcommands — one Typer per platform
platform_apps: dict[str, typer.Typer] = {}
for _pname in ("opencode", "codex", "copilot"):
    _plat = typer.Typer(
        name=_pname, help=f"Manage Cortex integration with {_pname}", no_args_is_help=True
    )
    platform_apps[_pname] = _plat
    app.add_typer(_plat, name=_pname)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _error(what: str, why: str, fix: str) -> None:
    """Print a structured error message."""
    typer.echo(f"\n  What failed:\n    {what}\n", err=True)
    typer.echo(f"  Why it matters:\n    {why}\n", err=True)
    typer.echo(f"  Suggested fix:\n    {fix}\n", err=True)


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
    repo_root: str | None = typer.Argument(
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
        _error(
            "python3 not found on PATH",
            "Cortex requires Python 3.10+ to create a venv and run the encoder.",
            "Install Python 3.10+ and ensure 'python3' is on your PATH.",
        )
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

    typer.echo("\nBootstrap complete. Activate with:")
    typer.echo(f"  source {venv_dir}/bin/activate")
    typer.echo("  cortex install")


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------


@app.command()
def install(
    vault: str | None = typer.Argument(
        None,
        help="Vault path (default: auto-detect or prompt)",
    ),
    upgrade: bool = typer.Option(
        False,
        "--upgrade",
        help="Upgrade an existing install",
    ),
    no_encode: bool = typer.Option(
        False,
        "--no-encode",
        help="Skip re-encoding after install/upgrade",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would change without writing anything",
    ),
) -> None:
    """Bootstrap or upgrade Cortex for a user.

    Handles everything: venv deps, config generation, skill installation,
    backup, and encoding.
    """
    repo_root = _REPO_ROOT

    if not vault:
        vault = typer.prompt("Vault path", default=str(_find_vault()))
    vault_path = Path(vault).expanduser()

    if not vault_path.exists():
        _error(
            f"Vault path does not exist: {vault_path}",
            "The vault directory must exist before Cortex can install into it.",
            f"Create the directory first: mkdir -p {vault_path}",
        )
        raise typer.Exit(code=1)

    vault_path = vault_path.resolve()
    sync_dir = vault_path / "_sync"
    encoded_dir = sync_dir / "encoded"
    skills_dir = encoded_dir / "skills"
    memory_json = encoded_dir / "memory.json"
    core_context = encoded_dir / "opencode" / "core-context.md"
    projects_dir = encoded_dir / "opencode" / "projects"
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
    verb = "upgrade" if upgrade else "install"
    typer.echo(f"==> Cortex {verb} [{mode}] (v{rel_ver}, schema v{schema_ver})")
    typer.echo(f"    vault: {vault_path}")

    # ---- Version guard (upgrade only) ----
    if upgrade:
        live_schema = read_vault_schema(vault_path)
        if live_schema is not None and live_schema > schema_ver:
            _error(
                f"Live vault schema (v{live_schema}) is NEWER than this code (v{schema_ver})",
                "Downgrading the schema would risk data loss in your vault.",
                "Update Cortex code to at least v{live_schema}, or back up and recreate the vault.",
            )
            raise typer.Exit(code=1)

    python = sys.executable

    # ---- [1/4] Ensure venv deps ----
    typer.echo("\n==> [1/4] Dependencies")
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

    # ---- [2/4] Config (only if missing) ----
    typer.echo("\n==> [2/4] Config")
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

    # ---- [3/4] Skill + first encode ----
    typer.echo("\n==> [3/4] Skill + encode")
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
                _record_action(actions_file, "modified", str(skill_dest), "cortex-ai.SKILL.md.bak")
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

    # Run encode
    if not dry_run and config_file.exists():
        rc = run_encode(config_path=config_file)
        if rc != 0:
            typer.echo("    WARNING: encode had errors", err=True)

    # ---- [4/4] Re-encode if upgrade ----
    if upgrade and not no_encode and not dry_run:
        typer.echo("\n==> [4/4] Re-encode")
        rc = run_encode(config_path=config_file)
        if rc != 0:
            typer.echo("    WARNING: re-encode had errors", err=True)
        typer.echo("    Re-encoded after upgrade")
    elif not upgrade:
        typer.echo("\n==> [4/4] (skipped — initial install)")

    # ---- Write manifest ----
    if not dry_run:
        _write_manifest(
            manifest_dir / "manifest.json", actions_file, str(vault_path), str(repo_root)
        )
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
        typer.echo("  cortex status         # verify the install")
        typer.echo("  cortex version        # show version info")
        typer.echo("  cortex import --dry-run  # import existing agent context")
        typer.echo("  cortex encode        # run encoding manually")


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
    backup: str | None = typer.Option(
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
        help="Also delete _sync/encoded (notes are kept)",
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
# encode
# ---------------------------------------------------------------------------


@app.command()
def encode(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show changes without writing"),
    list_notes: bool = typer.Option(False, "--list", help="List all vault notes with tier/type"),
    show_config: bool = typer.Option(False, "--show-config", help="Print resolved paths as JSON"),
    check: bool = typer.Option(False, "--check", help="Report version/schema health and exit"),
    graph: bool = typer.Option(False, "--graph", help="Output wiki-link graph and exit"),
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
    hive_push: bool = typer.Option(False, "--hive-push", help="Push vault notes to hub"),
    hive_pull: bool = typer.Option(False, "--hive-pull", help="Pull vault notes from hub"),
    hive_status: bool = typer.Option(False, "--hive-status", help="Show hive connection status"),
    config_path: str | None = typer.Option(
        None,
        "--config",
        help="Path to cortex.yaml config file",
    ),
) -> None:
    """Run the vault-to-agent encoding process."""
    cfg_path = Path(config_path) if config_path else Path.cwd() / "_sync" / "cortex.yaml"
    rc = run_encode(
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
    vault: str | None = typer.Option(
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
            mem_json = vp / "_sync" / "encoded" / "memory.json"
            if mem_json.exists():
                typer.echo("Encoded memory:   found")
                schema = read_vault_schema(vp)
                code_schema = schema_version()
                if schema is None:
                    typer.echo("Schema:           unknown (fresh vault?)")
                elif schema == code_schema:
                    typer.echo("Schema:           compatible")
                elif schema < code_schema:
                    typer.echo(f"Schema:           migration pending (v{schema} -> v{code_schema})")
                else:
                    typer.echo(
                        "Schema:           ERROR — vault newer than code",
                        err=True,
                    )
            else:
                typer.echo("Encoded memory:   MISSING — run 'cortex encode'")

            # Check opencode config exists
            opencode_cfg = Path.home() / ".config" / "opencode" / "opencode.jsonc"
            if not opencode_cfg.exists():
                opencode_cfg = Path.home() / ".config" / "opencode" / "opencode.json"
            env_cfg = os.environ.get("OPENCODE_CONFIG")
            if env_cfg:
                opencode_cfg = Path(env_cfg)
            if opencode_cfg.exists():
                typer.echo("opencode config:  found")
            else:
                typer.echo("opencode config:  not found")

            typer.echo(
                "\nStatus:           HEALTHY"
                if vp.exists() and mem_json.exists()
                else "\nStatus:           NEEDS ATTENTION"
            )
        except Exception as e:
            _error(
                f"Could not read config: {e}",
                "The config file is present but unreadable, so Cortex cannot "
                "locate the vault or validate the installation.",
                "Check file permissions and ensure cortex.yaml is valid YAML.",
            )
            raise typer.Exit(code=1) from None
    else:
        _error(
            "Config not found",
            "Cortex needs a cortex.yaml config to locate the vault and run encoding.",
            "Run 'cortex install' to set up Cortex.",
        )
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# import
# ---------------------------------------------------------------------------


@app.command(name="import")
def import_cmd(
    vault: str | None = typer.Option(
        None,
        "--vault",
        help="Vault root to import into (default: auto-detect)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would happen without writing anything",
    ),
    agents_md: str | None = typer.Option(None, "--agents-md", help="Path to AGENTS.md"),
    claude_md: str | None = typer.Option(None, "--claude-md", help="Path to CLAUDE.md"),
    opencode: str | None = typer.Option(None, "--opencode", help="Path to opencode.jsonc"),
    claude_memory: str | None = typer.Option(
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
# init
# ---------------------------------------------------------------------------


@app.command()
def init(
    vault: str | None = typer.Argument(
        None,
        help="Vault path (default: current directory)",
    ),
    template: str | None = typer.Option(
        None,
        "--template",
        "-t",
        help="Starter template (personal, engineering, product-management, knowledge-base)",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
) -> None:
    """Initialize a new Cortex vault with starter notes."""
    from cortex.templates._render import TEMPLATES, apply_template, list_templates

    vault_path = Path(vault) if vault else Path.cwd()

    if template is None:
        typer.echo("Available templates:\n")
        for name, desc in list_templates().items():
            typer.echo(f"  {name:24s} {desc}")
        typer.echo(f"\nUsage: cortex init --template <name> {vault_path}")
        return

    if template not in TEMPLATES:
        _error(
            f"Unknown template: {template!r}",
            f"Available templates: {', '.join(TEMPLATES)}",
            "Run 'cortex init' to see available templates.",
        )
        raise typer.Exit(code=1)

    mode = "DRY-RUN" if dry_run else "APPLY"
    typer.echo(f"==> Cortex init [{mode}] (template: {template})")
    typer.echo(f"    vault: {vault_path}\n")

    created = apply_template(vault_path, template, dry_run=dry_run)

    if not created:
        typer.echo("  No files created (all already exist).")
    else:
        for rel in created:
            typer.echo(f"  Created: {rel}")
        typer.echo(f"\n  {len(created)} file(s) created.")

    typer.echo("\nNext steps:")
    typer.echo(f"  1. Review and customize the notes in {vault_path}")
    typer.echo(f"  2. Run 'cortex install {vault_path}' to set up Cortex")


# ---------------------------------------------------------------------------
# memory helpers
# ---------------------------------------------------------------------------


def _find_memory_json(vault: str | None) -> Path | None:
    """Locate memory.json from --vault option or common locations."""
    if vault:
        vp = Path(vault).expanduser()
        mp = vp / "_sync" / "encoded" / "memory.json"
        if mp.exists():
            return mp
        return mp  # return path even if missing — caller handles
    for p in [Path.cwd(), Path.home() / "Cortex"]:
        mp = p / "_sync" / "encoded" / "memory.json"
        if mp.exists():
            return mp
    return None


def _find_vault_path(vault: str | None) -> Path | None:
    """Locate vault root from --vault option or common locations."""
    if vault:
        return Path(vault).expanduser()
    for p in [Path.cwd(), Path.home() / "Cortex"]:
        if (p / "_sync" / "cortex.yaml").exists():
            return p
    return None


def _scan_vault_for_note(vault_root: Path, note_id: str) -> Path | None:
    """Walk the vault looking for <note_id>.md in any subdirectory."""
    for md_file in vault_root.rglob(f"{note_id}.md"):
        # skip dot-dirs and _sync
        parts = md_file.relative_to(vault_root).parts
        if any(p.startswith((".", "_")) for p in parts):
            continue
        return md_file
    return None


def _print_note(note_id: str, note: dict) -> None:
    """Pretty-print a note dict from memory.json."""
    typer.echo(f"# {note_id}")
    typer.echo(f"**Type:** {note.get('type', '?')}")
    typer.echo(f"**Category:** {note.get('category', '')}")
    typer.echo(f"**Tier:** {note.get('tier', '')}")
    updated = note.get("updated", "")
    if updated:
        typer.echo(f"**Updated:** {updated}")
    aliases = note.get("aliases", [])
    if aliases:
        typer.echo(f"**Aliases:** {', '.join(aliases)}")
    tags = note.get("tags", [])
    if tags:
        typer.echo(f"**Tags:** {', '.join(tags)}")
    body = note.get("content", "")
    if body:
        typer.echo("")
        typer.echo(body)


def _print_note_from_vault_file(vault_root: Path, note_id: str) -> None:
    """Find and print a note by scanning vault files."""
    file_path = _scan_vault_for_note(vault_root, note_id)
    if file_path is None:
        _error(
            f"Note '{note_id}' not found in vault",
            f"No file named {note_id}.md found in {vault_root}",
            "Check the id for typos, or run 'cortex encode' first.",
        )
        raise typer.Exit(code=1)

    content = file_path.read_text(encoding="utf-8")
    typer.echo(f"# {note_id} (from vault file)")
    typer.echo(f"**Path:** {file_path}")
    typer.echo("")
    typer.echo(content)


# ---------------------------------------------------------------------------
# memory subcommands
# ---------------------------------------------------------------------------


@memory_app.command()
def get(
    note_id: str = typer.Argument(..., help="Note id slug (e.g. 'askdel', 'jira-rest-api')"),
    vault: str | None = typer.Option(None, "--vault", help="Vault path (auto-detect by default)"),
) -> None:
    """Fetch a single memory note by its id from memory.json or vault files."""
    # Find memory.json
    mem_path = _find_memory_json(vault)

    if not mem_path or not mem_path.exists():
        # Fall back to vault file scan
        vault_path = _find_vault_path(vault)
        if vault_path is not None:
            _print_note_from_vault_file(vault_path, note_id)
            return
        _error(
            "memory.json not found and no vault path available",
            "A memory index or vault directory is needed to retrieve a note.",
            "Run 'cortex encode' to generate memory.json, or specify --vault.",
        )
        raise typer.Exit(code=1)

    try:
        data = json.loads(mem_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        _error(
            f"Could not read memory.json: {e}",
            "The memory index file exists but is unreadable or contains invalid JSON.",
            "Run 'cortex encode' to regenerate memory.json.",
        )
        raise typer.Exit(code=1) from e

    notes = data.get("notes", {})
    note = notes.get(note_id)
    if note is not None:
        _print_note(note_id, note)
        return

    # Not in memory.json — try vault file fallback
    vault_path = _find_vault_path(vault)
    if vault_path is not None:
        _print_note_from_vault_file(vault_path, note_id)
        return

    _error(
        f"Note '{note_id}' not found",
        "The note was not found in memory.json or the vault directory.",
        "Check the id for typos. Use 'cortex memory search' to find available notes.",
    )
    raise typer.Exit(code=1)


@memory_app.command()
def search(
    query: str = typer.Argument(..., help="Search query string"),
    vault: str | None = typer.Option(None, "--vault", help="Vault path (auto-detect by default)"),
) -> None:
    """Search encoded memory from the CLI."""
    mem_path = _find_memory_json(vault)

    if not mem_path or not mem_path.exists():
        _error(
            "memory.json not found",
            "The encoded memory index is required to search notes.",
            "Run 'cortex encode' to generate memory.json from your vault notes.",
        )
        raise typer.Exit(code=1)

    try:
        data = json.loads(mem_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        _error(
            f"Could not read memory.json: {e}",
            "The memory index file exists but is unreadable or contains invalid JSON.",
            "Run 'cortex encode' to regenerate memory.json.",
        )
        raise typer.Exit(code=1) from e

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
    for _score, nid, note in results[:20]:
        alias = note.get("aliases", [""])[0]
        cat = note.get("category", "")
        snippet = note.get("content", "")[:80].replace("\n", " ")
        typer.echo(f"  {nid}  · {note.get('type', '?')}/{cat}  · {alias}")
        if snippet:
            typer.echo(f"    {snippet}...")


@memory_app.command()
def write(
    title: str = typer.Option(..., "--title", help="Note title (becomes alias and id)"),
    note_type: str = typer.Option(
        ..., "--type", help="Note type (knowledge, entity, feedback, etc.)"
    ),
    tier: str = typer.Option(..., "--tier", help="Tier (core, skill:<name>, project, vault-only)"),
    tags: str | None = typer.Option(None, "--tags", help="Comma-separated tags"),
    category: str | None = typer.Option(
        None, "--category", help="Category (patterns, api, projects, etc.)"
    ),
    body: str | None = typer.Option(None, "--body", help="Note body content (inline text)"),
    body_file: str | None = typer.Option(
        None, "--body-file", help="Path to file containing note body content"
    ),
    update: bool = typer.Option(
        False, "--update", help="Update an existing note (patch body + bump date)"
    ),
    no_encode: bool = typer.Option(False, "--no-encode", help="Skip automatic encode after write"),
    vault: str | None = typer.Option(None, "--vault", help="Vault path (auto-detect by default)"),
) -> None:
    """Write a memory note to the vault. Without --body/--body-file, writes frontmatter only."""
    # Validate mutually exclusive body options
    if body and body_file:
        _error(
            "Conflicting body options",
            "Both --body and --body-file were provided.",
            "Use one or the other, not both.",
        )
        raise typer.Exit(code=1)

    # Find vault
    vault_path = _find_vault_path(vault)
    if not vault_path or not vault_path.exists():
        _error(
            "Vault not found",
            "A vault directory is required to write notes into.",
            "Run 'cortex install' first, or pass --vault to specify the vault path.",
        )
        raise typer.Exit(code=1)

    note_id = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    if not note_id:
        note_id = "untitled"

    today = datetime.now().strftime("%Y-%m-%d")

    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    # Determine type directory
    type_dir_name = note_type + ("s" if not note_type.endswith("s") else "")
    target_dir = vault_path / type_dir_name
    target_dir.mkdir(parents=True, exist_ok=True)

    note_path = target_dir / f"{note_id}.md"

    if note_path.exists():
        if not update:
            _error(
                f"Note already exists at {note_path}",
                "Overwriting an existing note would lose its current content.",
                "Use --update to patch the existing note, or use a different --title.",
            )
            raise typer.Exit(code=1)
        # Update mode: patch body and bump date
        existing = note_path.read_text(encoding="utf-8")
        frontmatter, _ = _split_frontmatter(existing)
        body_text = _read_body(body, body_file)
        new_content = _build_note_content(
            note_id, note_type, tier, title, today, category, tag_list, body_text
        )
        note_path.write_text(new_content, encoding="utf-8")
        typer.echo(f"Updated note: {note_path}")
    else:
        if update:
            _error(
                f"Note does not exist at {note_path}",
                "--update was passed but no existing note was found.",
                "Remove --update to create a new note, or check the --title value.",
            )
            raise typer.Exit(code=1)
        body_text = _read_body(body, body_file)
        content = _build_note_content(
            note_id, note_type, tier, title, today, category, tag_list, body_text
        )
        note_path.write_text(content, encoding="utf-8")
        typer.echo(f"Created note: {note_path}")

    typer.echo(f"  id: {note_id}")
    typer.echo(f"  type: {note_type}  tier: {tier}")
    if tag_list:
        typer.echo(f"  tags: {tag_list}")
    if body is not None or body_file is not None:
        typer.echo("  body: included")

    if not no_encode:
        _fire_encode(vault_path)


def _read_body(body: str | None, body_file: str | None) -> str:
    """Read body content from inline text or file."""
    if body is not None:
        return body
    if body_file is not None:
        bf = Path(body_file).expanduser()
        if not bf.exists():
            _error(
                f"Body file not found: {bf}",
                "The --body-file path does not exist.",
                "Check the path and try again.",
            )
            raise typer.Exit(code=1)
        return bf.read_text(encoding="utf-8")
    return ""


def _split_frontmatter(content: str) -> tuple[str, str]:
    """Split markdown content into frontmatter and body."""
    parts = content.split("---", 2)
    if len(parts) >= 3:
        return parts[0] + "---" + parts[1] + "---\n", parts[2]
    return "", content


def _build_note_content(
    note_id: str,
    note_type: str,
    tier: str,
    title: str,
    today: str,
    category: str | None,
    tag_list: list[str],
    body_text: str,
) -> str:
    """Build markdown content with YAML frontmatter and optional body."""
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
    if body_text:
        parts.append(body_text)
        if not body_text.endswith("\n"):
            parts.append("")
    return "\n".join(parts)


def _resolve_encode_python(vault_root: Path) -> str:
    """Find the Python interpreter for the encoder venv (cross-platform)."""
    # 1. ENCODE_PYTHON env var override
    if env_python := os.environ.get("ENCODE_PYTHON"):
        return env_python
    # 2. Cross-platform venv detection
    for candidate in [
        vault_root / "_sync" / ".venv" / "bin" / "python",
        vault_root / "_sync" / ".venv" / "Scripts" / "python.exe",
    ]:
        if candidate.exists():
            return str(candidate)
    # 3. Fallback
    for fallback in ["python3", "python"]:
        if shutil.which(fallback):
            return fallback
    return "python3"


def _fire_encode(vault_root: Path) -> None:
    """Fire-and-forget encode after a write, so memory.json stays current."""
    python = _resolve_encode_python(vault_root)
    try:
        subprocess.Popen(
            [python, "-m", "cortex.encoder.core"],
            cwd=str(vault_root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass  # encode is best-effort


# ---------------------------------------------------------------------------
# Platform commands: cortex <platform> install/uninstall/status
# ---------------------------------------------------------------------------


def _build_context(vault: str | None, dry_run: bool = False):
    """Build an InstallContext from CLI args."""
    from cortex.platforms.base import InstallContext

    vault_path = Path(vault) if vault else _find_vault()
    config_path = vault_path / "_sync" / "cortex.yaml"
    skills_dir = Path.home() / ".config" / "opencode" / "skills"
    return InstallContext(
        repo_root=_REPO_ROOT,
        vault_root=vault_path,
        config_path=config_path,
        skills_dir=skills_dir,
        dry_run=dry_run,
    )


def _add_platform_commands(platform_name: str) -> None:
    """Register install/uninstall/status commands on a platform's Typer app."""
    from cortex.platforms.registry import get_installer

    plat_app = platform_apps[platform_name]
    installer = get_installer(platform_name)
    if installer is None:
        return

    @plat_app.command(name="install")
    def _install(
        vault: str | None = typer.Option(None, "--vault", help="Vault path"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
    ) -> None:
        ctx = _build_context(vault, dry_run)
        mode = "DRY-RUN" if dry_run else "APPLY"
        typer.echo(f"==> {installer.platform_name} install [{mode}]")
        if not installer.detect():
            typer.echo(
                f"WARNING: {installer.platform_name} config not detected at expected location",
                err=True,
            )
        result = installer.install(ctx)
        typer.echo(result.summary(dry_run))
        if not dry_run and result.changed:
            typer.echo(f"\nInstalled Cortex for {installer.platform_name}.")
        elif dry_run and result.changed:
            typer.echo(f"\nWould install Cortex for {installer.platform_name}.")

    @plat_app.command(name="uninstall")
    def _uninstall(
        vault: str | None = typer.Option(None, "--vault", help="Vault path"),
        dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing"),
    ) -> None:
        ctx = _build_context(vault, dry_run)
        mode = "DRY-RUN" if dry_run else "APPLY"
        typer.echo(f"==> {installer.platform_name} uninstall [{mode}]")
        result = installer.uninstall(ctx)
        typer.echo(result.summary(dry_run))
        if result.changed:
            typer.echo(f"\nRemoved Cortex assets for {installer.platform_name}.")

    @plat_app.command(name="status")
    def _status(
        vault: str | None = typer.Option(None, "--vault", help="Vault path"),
    ) -> None:
        ctx = _build_context(vault)
        detected = installer.detect()
        errors = installer.validate(ctx)
        typer.echo(f"Platform: {installer.platform_name}")
        typer.echo(f"Detected: {'yes' if detected else 'no'}")
        if errors:
            for e in errors:
                typer.echo(f"  ✗ {e}")
            typer.echo("Status: NEEDS ATTENTION")
        else:
            typer.echo("Status: HEALTHY")


for _pname in platform_apps:
    _add_platform_commands(_pname)


# ---------------------------------------------------------------------------
# cortex doctor
# ---------------------------------------------------------------------------


@app.command()
def doctor(
    platform: str | None = typer.Option(None, "--platform", help="Check a specific platform only"),
    vault: str | None = typer.Option(None, "--vault", help="Vault path"),
) -> None:
    """Validate Cortex installation across all platforms."""
    from cortex.platforms.registry import get_installer, list_platforms

    vault_path = Path(vault) if vault else _find_vault()
    typer.echo("Cortex doctor\n")

    all_healthy = True

    # ---- Core section ----
    typer.echo("Core")

    # Python version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 10)
    typer.echo(f"  {'✓' if py_ok else '✗'} Python {py_ver} (>= 3.10)")
    if not py_ok:
        all_healthy = False

    # Config
    config_path = vault_path / "_sync" / "cortex.yaml"
    cfg_ok = config_path.exists()
    typer.echo(f"  {'✓' if cfg_ok else '✗'} Config found at {config_path}")
    if not cfg_ok:
        typer.echo("    Suggested fix: Run 'cortex install' to set up Cortex")
        all_healthy = False

    # Vault writable
    vault_ok = vault_path.exists() and os.access(vault_path, os.W_OK)
    vault_label = "writable" if vault_ok else "not writable"
    typer.echo(f"  {'✓' if vault_ok else '✗'} Vault {vault_label} at {vault_path}")
    if not vault_ok:
        typer.echo("    Suggested fix: Ensure the vault directory exists and is writable")
        all_healthy = False

    # Schema compatibility
    if cfg_ok:
        live_schema = read_vault_schema(vault_path)
        code_schema = schema_version()
        if live_schema is None:
            typer.echo("  ✓ Schema v? (fresh vault, no prior schema)")
        elif live_schema == code_schema:
            typer.echo(f"  ✓ Schema v{live_schema} (compatible)")
        elif live_schema < code_schema:
            typer.echo(f"  ⚠ Schema v{live_schema} (migration pending → v{code_schema})")
        else:
            typer.echo(f"  ✗ Schema v{live_schema} > code v{code_schema} (vault newer than code)")
            all_healthy = False
    else:
        typer.echo("  ○ Schema (skipped — config not found)")

    # Encoded memory
    mem_json = vault_path / "_sync" / "encoded" / "memory.json"
    if mem_json.exists():
        # Check freshness
        mtime = mem_json.stat().st_mtime
        age_seconds = datetime.now().timestamp() - mtime
        age_days = age_seconds / 86400
        if age_days < 1:
            age_str = f"{int(age_seconds / 3600)}h ago"
        elif age_days < 2:
            age_str = "1 day ago"
        else:
            age_str = f"{int(age_days)} days ago"
        fresh = age_days <= 7
        mem_label = "current" if fresh else "stale"
        typer.echo(f"  {'✓' if fresh else '⚠'} Encoded memory {mem_label} (encoded {age_str})")
        if not fresh:
            typer.echo("    Suggested fix: Run 'cortex encode' to refresh memory")
    else:
        typer.echo("  ✗ Encoded memory not found")
        typer.echo("    Suggested fix: Run 'cortex encode'")
        all_healthy = False

    # Memory file validity
    if mem_json.exists():
        try:
            data = json.loads(mem_json.read_text(encoding="utf-8"))
            note_count = len(data.get("notes", {}))
            typer.echo(f"  ✓ Memory file valid ({note_count} notes)")
        except (OSError, json.JSONDecodeError) as e:
            typer.echo(f"  ✗ Memory file invalid: {e}")
            typer.echo("    Suggested fix: Run 'cortex encode' to regenerate")
            all_healthy = False
    else:
        typer.echo("  ○ Memory file (skipped — encoded memory not found)")

    # Skill installed
    skill_file = Path.home() / ".config" / "opencode" / "skills" / "cortex-ai" / "SKILL.md"
    skill_ok = skill_file.exists()
    typer.echo(f"  {'✓' if skill_ok else '✗'} Skill installed")
    if not skill_ok:
        typer.echo("    Suggested fix: Run 'cortex install' to install the skill")

    # ---- Platform section ----
    platforms_to_check = list_platforms()
    if platform:
        inst = get_installer(platform)
        if inst is None:
            typer.echo(f"\nUnknown platform: {platform}")
            typer.echo(f"Available: {', '.join(p.platform_name for p in list_platforms())}")
            raise typer.Exit(code=1)
        platforms_to_check = [inst]

    for inst in platforms_to_check:
        typer.echo(f"\n{inst.platform_name.title()}")
        detected = inst.detect()
        typer.echo(f"  {'✓' if detected else '○'} Detected")
        if detected:
            ctx = _build_context(vault)
            errors = inst.validate(ctx)
            if errors:
                for err in errors:
                    typer.echo(f"  ✗ {err}")
                all_healthy = False
            else:
                typer.echo("  ✓ Skill installed")

    # ---- Summary ----
    typer.echo(f"\nStatus: {'HEALTHY' if all_healthy else 'NEEDS ATTENTION'}")
    if not all_healthy:
        typer.echo("Run 'cortex install' to fix issues.")


# ---------------------------------------------------------------------------
# cortex upgrade
# ---------------------------------------------------------------------------


@app.command()
def upgrade(
    vault: str | None = typer.Option(None, "--vault", help="Vault path override"),
    apply: bool = typer.Option(False, "--apply", help="Apply changes (default is preview)"),
) -> None:
    """Re-encode memory and refresh Cortex assets.

    Default is dry-run (preview only). Pass --apply to make changes.
    """
    vault_path = Path(vault) if vault else _find_vault()
    sync_dir = vault_path / "_sync"
    config_file = sync_dir / "cortex.yaml"

    if not vault_path.exists():
        _error(
            f"Vault path does not exist: {vault_path}",
            "Cannot upgrade without a valid vault directory.",
            "Run 'cortex install' to set up a new vault.",
        )
        raise typer.Exit(code=1)

    if not config_file.exists():
        _error(
            f"Config not found at {config_file}",
            "Cannot upgrade without a cortex.yaml config.",
            "Run 'cortex install' to create the config.",
        )
        raise typer.Exit(code=1)

    # Schema check
    live_schema = read_vault_schema(vault_path)
    code_schema = schema_version()
    schema_changed = live_schema is not None and live_schema != code_schema

    # Backup directory
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = sync_dir / "backups" / f"{stamp}-upgrade"

    typer.echo(f"Cortex upgrade{' preview' if not apply else ''}\n".rstrip())

    # Backup
    if not apply:
        typer.echo(f"  Would backup: {sync_dir}")
    else:
        backup_dir.mkdir(parents=True, exist_ok=True)
        # Backup the encoded directory and config
        for fname in ["cortex.yaml"]:
            _backup_file(sync_dir / fname, backup_dir)
        encoded = sync_dir / "encoded"
        if encoded.exists():
            for item in encoded.iterdir():
                _backup_file(item, backup_dir / "encoded")
        typer.echo(f"  Backed up: {backup_dir}")

    # Schema
    if live_schema is None:
        typer.echo("  Schema: unknown (fresh vault)")
    elif schema_changed:
        typer.echo(f"  Schema: {live_schema} -> {code_schema} (change detected)")
        typer.echo("  Warning: automated migration is not supported. See docs/migration.md.")
    else:
        typer.echo(f"  Schema: {code_schema} (unchanged)")

    # Re-encode
    if not apply:
        typer.echo("  Would re-encode memory")
    else:
        rc = run_encode(config_path=config_file)
        if rc != 0:
            typer.echo("  WARNING: encode had errors", err=True)
        else:
            typer.echo("  Re-encoded memory")

    typer.echo("")
    if not apply:
        typer.echo("Run 'cortex upgrade --apply' to apply changes.")
    else:
        typer.echo("Upgrade complete. Restart your agent to load changes.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    app()


if __name__ == "__main__":
    main()

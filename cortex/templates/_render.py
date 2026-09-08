"""Render a starter vault from a template name.

Templates live in subdirectories of this package. Each template has a
``structure.py`` that returns a dict of {relative_path: file_content}.
"""

from __future__ import annotations

import importlib
from pathlib import Path

TEMPLATES = {
    "personal": "Personal vault — preferences, notes, and personal projects.",
    "engineering": "Engineering vault — code patterns, architecture decisions, and tech debt.",
    "product-management": "Product vault — roadmaps, requirements, and stakeholder notes.",
    "knowledge-base": "Knowledge base — reference docs, procedures, and learning notes.",
}


def list_templates() -> dict[str, str]:
    """Return {name: description} for all available templates."""
    return dict(TEMPLATES)


def render_template(name: str) -> dict[str, str]:
    """Return {relative_path: content} for the named template.

    Raises ``ValueError`` if the template name is unknown.
    """
    if name not in TEMPLATES:
        raise ValueError(f"Unknown template: {name!r}. Available: {', '.join(TEMPLATES)}")
    mod = importlib.import_module(f"cortex.templates.{name.replace('-', '_')}")
    return mod.structure()  # type: ignore[no-any-return]


def apply_template(vault_path: Path, name: str, *, dry_run: bool = False) -> list[str]:
    """Write the named template into *vault_path*.

    Returns a list of relative paths that were created (or would be created
    in dry-run mode).  Never overwrites an existing file — skips instead.
    """
    files = render_template(name)
    created: list[str] = []
    for rel, content in files.items():
        target = vault_path / rel
        if target.exists():
            continue
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        created.append(rel)
    return created


def apply_core_notes(vault_path: Path, *, dry_run: bool = False) -> list[str]:
    """Write Cortex system notes (capture rules, retrieval priority) into *vault_path*.

    Called by ``cortex init`` before the user-chosen template, and by
    ``cortex install`` so the rules ship even for vaults that skip init.
    Returns a list of relative paths created (or would be created in dry-run
    mode). Never overwrites an existing file — safe to call on upgrade.
    """
    from cortex.templates.core_notes import structure

    created: list[str] = []
    for rel, content in structure().items():
        target = vault_path / rel
        if target.exists():
            continue
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        created.append(rel)
    return created

#! /usr/bin/env python3
"""
cortex.vault.links — Wiki-link parsing and resolution.

Shared between the encoder (build_wiki_graph) and the lint command
(dangling-wiki-link rule). Kept here so both can import the same
logic without the encoder dragging in heavy dependencies.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Low-level link parsing
# ---------------------------------------------------------------------------


def extract_wiki_links(text: str) -> list[str]:
    """Extract target ids from [[wiki-link]] syntax in a note body."""
    links = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", text)
    return links


def strip_wiki_links(text: str) -> str:
    """Replace [[link]] and [[link|label]] with display text."""
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    return text


# ---------------------------------------------------------------------------
# Cross-note link resolution
# ---------------------------------------------------------------------------


def resolve_wiki_links(
    notes: list,
    *,
    id_attr: str = "name",
    aliases_attr: str = "aliases",
    body_attr: str = "body",
) -> tuple[list[dict], list[dict]]:
    """Parse [[wiki-links]] from all note bodies and resolve them.

    Parameters
    ----------
    notes : list
        Any iterable of objects that have ``id_attr`` (str), ``aliases_attr``
        (list[str]), and ``body_attr`` (str) attributes.
    id_attr, aliases_attr, body_attr : str
        Attribute names to use — makes this work with VaultNote, dataclasses,
        or dicts alike.

    Returns
    -------
    edges : list[dict]
        Resolved link edges: ``[{"source": "...", "target": "..."}, ...]``
    dangling : list[dict]
        Unresolved links: ``[{"note": "...", "target": "..."}, ...]``
    """
    # Build id set and alias map
    id_set: set[str] = set()
    id_aliases: dict[str, str] = {}
    for n in notes:
        nid = getattr(n, id_attr)
        id_set.add(nid)
        for alias in getattr(n, aliases_attr, []):
            id_aliases[alias.lower()] = nid

    edges: list[dict] = []
    dangling: list[dict] = []

    for n in notes:
        raw_links = extract_wiki_links(getattr(n, body_attr))
        seen_targets: set[str] = set()
        for target in raw_links:
            resolved = _resolve_single_link(target, id_set, id_aliases)
            if not resolved:
                dangling.append({"note": getattr(n, id_attr), "target": target})
                continue
            if resolved == getattr(n, id_attr):
                continue
            if resolved in seen_targets:
                continue
            seen_targets.add(resolved)
            edges.append({"source": getattr(n, id_attr), "target": resolved})

    return edges, dangling


def _resolve_single_link(
    target: str,
    id_set: set[str],
    id_aliases: dict[str, str],
) -> str | None:
    """Resolve a single wiki-link target to a note id, or None."""
    if target in id_set:
        return target
    if target.lower() in id_aliases:
        return id_aliases[target.lower()]
    # Case-insensitive fallback
    for nid in id_set:
        if nid.lower() == target.lower():
            return nid
    return None

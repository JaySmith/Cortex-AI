"""Config loading for the Cortex vault.

Shared by the encoder and CLI commands. Loads cortex.yaml and applies
defaults for optional blocks (hive, targets, etc.).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    sys.exit("ERROR: PyYAML is required.\n  pip install PyYAML>=6.0")


def load_config(config_file: Path) -> dict[str, Any]:
    """Load and return a cortex.yaml config dict. Exits on error."""
    if not config_file.exists():
        sys.exit(f"ERROR: Config not found: {config_file}")
    text = config_file.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        sys.exit(f"ERROR: Failed to parse {config_file}: {e}")
    data = data or {}
    # Apply hive defaults
    hive = data.get("hive", {})
    hive.setdefault("enabled", False)
    hive.setdefault("hub_url", "http://localhost:4096/mcp")
    hive.setdefault("machine_id", "")
    hive.setdefault("hub_token", "")
    hive.setdefault("replicate_tiers", ["core", "skill:*", "project"])
    hive.setdefault("sync_interval", 300)
    data["hive"] = hive
    return data

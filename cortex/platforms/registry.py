"""Platform registry — maps platform names to installers."""

from __future__ import annotations

from cortex.platforms.base import InstallerBase
from cortex.platforms.codex import CodexInstaller
from cortex.platforms.copilot import CopilotInstaller
from cortex.platforms.opencode import OpenCodeInstaller

_REGISTRY: dict[str, InstallerBase] = {}


def _register(installer: InstallerBase) -> None:
    _REGISTRY[installer.platform_name] = installer


_register(OpenCodeInstaller())
_register(CodexInstaller())
_register(CopilotInstaller())


def get_installer(name: str) -> InstallerBase | None:
    """Get an installer by platform name. Returns None if not found."""
    return _REGISTRY.get(name)


def list_platforms() -> list[InstallerBase]:
    """Return all registered installers."""
    return list(_REGISTRY.values())


def detect_platforms() -> list[InstallerBase]:
    """Return installers for platforms that appear to be installed."""
    return [p for p in _REGISTRY.values() if p.detect()]

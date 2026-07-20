"""Platform installers for Cortex — multi-agent support."""

from cortex.platforms.base import InstallContext, InstallerBase
from cortex.platforms.registry import detect_platforms, get_installer

__all__ = ["InstallerBase", "InstallContext", "detect_platforms", "get_installer"]

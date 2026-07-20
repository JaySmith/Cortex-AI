"""GitHub Copilot platform installer — Wave 1 stub."""

from __future__ import annotations

from pathlib import Path

from cortex.platforms.base import InstallContext, InstallerBase, InstallResult

COPILOT_CONFIG_DIR = Path.home() / ".github-copilot"


class CopilotInstaller(InstallerBase):
    platform_name = "copilot"
    description = "GitHub Copilot — AI pair programmer (stub, not yet implemented)"

    def detect(self) -> bool:
        return COPILOT_CONFIG_DIR.is_dir()

    def install(self, context: InstallContext) -> InstallResult:
        result = InstallResult()
        if not self.detect():
            raise RuntimeError(
                f"Copilot config directory not found: {COPILOT_CONFIG_DIR}\n"
                "Install GitHub Copilot first, then re-run this command."
            )
        # TODO Wave 2: generate Copilot-specific assets
        return result

    def uninstall(self, context: InstallContext) -> InstallResult:
        return InstallResult()

    def validate(self, context: InstallContext) -> list[str]:
        if not self.detect():
            return [f"Copilot config directory not found: {COPILOT_CONFIG_DIR}"]
        return []

"""Codex platform installer — Wave 1 stub."""

from __future__ import annotations

from pathlib import Path

from cortex.platforms.base import InstallContext, InstallerBase, InstallResult

CODEX_CONFIG_DIR = Path.home() / ".codex"


class CodexInstaller(InstallerBase):
    platform_name = "codex"
    description = "Codex — OpenAI's coding assistant (stub, not yet implemented)"

    def detect(self) -> bool:
        return CODEX_CONFIG_DIR.is_dir()

    def install(self, context: InstallContext) -> InstallResult:
        result = InstallResult()
        if not self.detect():
            raise RuntimeError(
                f"Codex config directory not found: {CODEX_CONFIG_DIR}\n"
                "Install Codex first, then re-run this command."
            )
        # TODO Wave 2: generate Codex-specific assets
        return result

    def uninstall(self, context: InstallContext) -> InstallResult:
        return InstallResult()

    def validate(self, context: InstallContext) -> list[str]:
        if not self.detect():
            return [f"Codex config directory not found: {CODEX_CONFIG_DIR}"]
        return []

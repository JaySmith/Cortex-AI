"""Base classes for platform installers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class InstallContext:
    """Everything an installer needs to do its work."""

    repo_root: Path
    vault_root: Path
    config_path: Path  # e.g. <vault>/_sync/cortex.yaml
    skills_dir: Path  # e.g. ~/.config/opencode/skills
    dry_run: bool = False
    backup_dir: Path | None = None  # where to stash backups


@dataclass
class InstallResult:
    """Summary of what an installer did (or would do in dry-run)."""

    created: list[Path] = field(default_factory=list)
    updated: list[Path] = field(default_factory=list)
    backed_up: list[Path] = field(default_factory=list)
    removed: list[Path] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.created or self.updated or self.removed)

    def summary(self, dry_run: bool = False) -> str:
        prefix = "Would" if dry_run else "Did"
        lines: list[str] = []
        for p in self.backed_up:
            lines.append(f"  backup: {p}")
        for p in self.created:
            lines.append(f"  {prefix.lower()} create: {p}")
        for p in self.updated:
            lines.append(f"  {prefix.lower()} update: {p}")
        for p in self.removed:
            lines.append(f"  {prefix.lower()} remove: {p}")
        if not lines:
            lines.append("  (no changes)")
        return "\n".join(lines)


# Managed block markers for Markdown files
BEGIN_MARKER = "<!-- BEGIN CORTEX MANAGED BLOCK -->"
END_MARKER = "<!-- END CORTEX MANAGED BLOCK -->"


def render_managed_block(content: str) -> str:
    """Wrap content in managed block markers."""
    return f"{BEGIN_MARKER}\n{content}\n{END_MARKER}"


def extract_managed_block(text: str) -> str | None:
    """Extract the content between managed block markers. Returns None if absent."""
    start = text.find(BEGIN_MARKER)
    end = text.find(END_MARKER)
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start + len(BEGIN_MARKER) : end].strip()


def upsert_managed_block(existing: str, new_content: str) -> str:
    """Replace or insert a managed block in existing file content.

    If a managed block exists, replace its contents. Otherwise, append
    the new block at the end of the file.
    """
    begin_idx = existing.find(BEGIN_MARKER)
    end_idx = existing.find(END_MARKER)

    block = render_managed_block(new_content)

    if begin_idx != -1 and end_idx != -1 and end_idx > begin_idx:
        # Replace existing block (include markers)
        return existing[:begin_idx] + block + existing[end_idx + len(END_MARKER) :]

    # No existing block — append
    suffix = "\n" if not existing.endswith("\n") else ""
    return existing + suffix + block + "\n"


class InstallerBase(ABC):
    """Abstract base for platform installers."""

    platform_name: str
    description: str

    @abstractmethod
    def detect(self) -> bool:
        """Return True if this platform appears to be installed or configured."""

    @abstractmethod
    def install(self, context: InstallContext) -> InstallResult:
        """Install Cortex assets for this platform. Returns what was done."""

    @abstractmethod
    def uninstall(self, context: InstallContext) -> InstallResult:
        """Remove Cortex-managed assets for this platform."""

    @abstractmethod
    def validate(self, context: InstallContext) -> list[str]:
        """Return a list of validation errors. Empty list means healthy."""

    def _backup(self, path: Path, context: InstallContext) -> Path | None:
        """Backup a file before modifying it. Returns backup path or None."""
        if not path.exists():
            return None
        if context.dry_run:
            return path  # pretend we backed it up
        backup_dir = context.backup_dir or context.vault_root / "_sync" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        import shutil

        flat = str(path).replace(str(Path.home()), "~").replace("/", "_").lstrip("_")
        backup_path = backup_dir / f"{flat}.bak"
        shutil.copy2(path, backup_path)
        return backup_path

    def _write_file(self, path: Path, content: str, context: InstallContext) -> bool:
        """Write a file, respecting dry_run. Returns True if file changed."""
        if context.dry_run:
            return not path.exists() or path.read_text(encoding="utf-8") != content
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.read_text(encoding="utf-8") == content:
            return False
        path.write_text(content, encoding="utf-8")
        return True

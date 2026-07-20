"""Tests for cortex upgrade command."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from cortex.cli.main import app

runner = CliRunner()


class TestUpgradePreview:
    def test_preview_shows_preview(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        vault.mkdir()
        sync = vault / "_sync"
        sync.mkdir()
        (sync / "cortex.yaml").write_text("vault_path: .")
        (sync / "SCHEMA_VERSION").write_text("2")

        result = runner.invoke(app, ["upgrade", "--vault", str(vault)])
        assert result.exit_code == 0
        assert "preview" in result.output.lower() or "Would backup" in result.output

    def test_preview_writes_nothing(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        vault.mkdir()
        sync = vault / "_sync"
        sync.mkdir()
        (sync / "cortex.yaml").write_text("vault_path: .")

        result = runner.invoke(app, ["upgrade", "--vault", str(vault)])
        assert result.exit_code == 0
        # No backups directory should be created
        backups = sync / "backups"
        assert not backups.exists()

    def test_missing_vault_shows_error(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["upgrade", "--vault", str(tmp_path / "nonexistent")])
        assert result.exit_code == 1
        assert "does not exist" in result.output.lower() or "What failed" in result.output

    def test_missing_config_shows_error(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        vault.mkdir()

        result = runner.invoke(app, ["upgrade", "--vault", str(vault)])
        assert result.exit_code == 1
        assert "config" in result.output.lower() or "What failed" in result.output.lower()


class TestUpgradeApply:
    def test_apply_creates_backup(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        vault.mkdir()
        sync = vault / "_sync"
        sync.mkdir()
        (sync / "cortex.yaml").write_text(
            f'vault_path: "{vault}"\n'
            f"targets:\n"
            f"  core_context:\n"
            f"    enabled: false\n"
            f"  skills:\n"
            f"    enabled: false\n"
            f"  projects:\n"
            f"    enabled: false\n"
            f"  python-agents:\n"
            f"    enabled: false\n"
        )
        (sync / "SCHEMA_VERSION").write_text("2")

        result = runner.invoke(app, ["upgrade", "--vault", str(vault), "--apply"])
        assert result.exit_code == 0
        assert "upgrade complete" in result.output.lower() or "Re-encoded" in result.output

        # Backups should exist
        backups = sync / "backups"
        assert backups.exists()
        backup_dirs = [d for d in backups.iterdir() if d.is_dir()]
        assert len(backup_dirs) >= 1

    def test_schema_unchanged_reported(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        vault.mkdir()
        sync = vault / "_sync"
        sync.mkdir()
        (sync / "cortex.yaml").write_text(
            f'vault_path: "{vault}"\n'
            f"targets:\n"
            f"  core_context:\n"
            f"    enabled: false\n"
            f"  skills:\n"
            f"    enabled: false\n"
            f"  projects:\n"
            f"    enabled: false\n"
            f"  python-agents:\n"
            f"    enabled: false\n"
        )
        (sync / "SCHEMA_VERSION").write_text("2")

        result = runner.invoke(app, ["upgrade", "--vault", str(vault), "--apply"])
        assert result.exit_code == 0
        assert "unchanged" in result.output.lower()

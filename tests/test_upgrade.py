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

    def test_schema_changed_message_is_accurate(self, tmp_path: Path) -> None:
        """When the vault schema differs from the code schema, the message must
        state that migration runs during re-encode — not the old, false
        "automated migration is not supported" warning.

        read_vault_schema reads _sync/encoded/memory.json (_meta.schema_version),
        so we stamp an older schema there to force the change-detected branch.
        """
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
        # Stamp an old schema so live != code triggers the change-detected branch.
        encoded = sync / "encoded"
        encoded.mkdir()
        (encoded / "memory.json").write_text('{"_meta": {"schema_version": 1}, "notes": {}}')

        result = runner.invoke(app, ["upgrade", "--vault", str(vault)])
        assert result.exit_code == 0
        assert "change detected" in result.output.lower()
        # Corrected messaging present...
        assert "migration will run automatically during re-encode" in result.output.lower()
        # ...and the old, misleading claim is gone.
        assert "not supported" not in result.output.lower()

    def test_apply_backs_up_nested_encoded_dirs(self, tmp_path: Path) -> None:
        """Regression: upgrade backup must handle subdirectories under
        _sync/encoded (e.g. encoded/projects/), not just top-level files.

        Previously _backup_file called shutil.copy2 on every entry, raising
        IsADirectoryError when it hit encoded/projects/.
        """
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

        # Reproduce the on-disk layout that triggered the crash: an encoded/
        # dir containing both a top-level file AND a nested subdirectory.
        encoded = sync / "encoded"
        (encoded / "projects").mkdir(parents=True)
        (encoded / "memory.json").write_text("{}")
        (encoded / "projects" / "kazi.md").write_text("# kazi\n")

        result = runner.invoke(app, ["upgrade", "--vault", str(vault), "--apply"])
        assert result.exit_code == 0, result.output

        # The nested file must be present in the backup snapshot.
        backups = sync / "backups"
        backup_dirs = [d for d in backups.iterdir() if d.is_dir()]
        assert len(backup_dirs) >= 1
        nested_copies = list(backups.rglob("kazi.md"))
        assert nested_copies, "nested encoded/projects file was not backed up"

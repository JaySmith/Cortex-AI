"""Tests for cortex doctor diagnostics."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from cortex.cli.main import app

runner = CliRunner()


class TestDoctorHealthy:
    def test_healthy_with_valid_install(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        vault.mkdir()
        sync = vault / "_sync"
        sync.mkdir()
        (sync / "cortex.yaml").write_text("vault_path: .")
        distilled = sync / "encoded"
        distilled.mkdir()
        (distilled / "memory.json").write_text('{"notes": {}, "_meta": {"schema_version": 2}}')

        result = runner.invoke(app, ["doctor", "--vault", str(vault)])
        assert result.exit_code == 0
        # Core checks should all pass
        assert "Python" in result.output
        assert "Config found" in result.output
        assert "Vault writable" in result.output
        assert "Schema" in result.output
        assert "Memory file valid" in result.output

    def test_doctor_shows_python_version(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        vault.mkdir()
        sync = vault / "_sync"
        sync.mkdir()
        (sync / "cortex.yaml").write_text("vault_path: .")

        result = runner.invoke(app, ["doctor", "--vault", str(vault)])
        assert result.exit_code == 0
        assert "Python" in result.output


class TestDoctorNeedsAttention:
    def test_missing_config(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        vault.mkdir()

        result = runner.invoke(app, ["doctor", "--vault", str(vault)])
        assert result.exit_code == 0
        assert "NEEDS ATTENTION" in result.output

    def test_missing_vault(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["doctor", "--vault", str(tmp_path / "nonexistent")])
        assert result.exit_code == 0
        assert "NEEDS ATTENTION" in result.output


class TestDoctorSpecificPlatform:
    def test_unknown_platform_exits(self) -> None:
        result = runner.invoke(app, ["doctor", "--platform", "nonexistent"])
        assert result.exit_code == 1
        assert "Unknown platform" in result.output or "unknown platform" in result.output.lower()

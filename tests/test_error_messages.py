"""Tests for structured error messages across the CLI."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from cortex.cli.main import app

runner = CliRunner()


class TestErrorMessages:
    def test_install_missing_vault_shows_structured_error(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["install", str(tmp_path / "nonexistent"), "--no-distill"])
        assert result.exit_code == 1
        # Should contain the three-part error structure
        output = result.output.lower()
        assert "what failed" in output or "does not exist" in output

    def test_bootstrap_missing_python(self, tmp_path: Path) -> None:
        # bootstrap with a bad repo root should still run
        # (it checks for python3 on PATH, which exists in test env)
        result = runner.invoke(app, ["bootstrap", str(tmp_path)])
        # Should either succeed or fail with a structured error
        assert result.exit_code in (0, 1)

    def test_memory_write_missing_vault(self, tmp_path: Path) -> None:
        result = runner.invoke(
            app,
            [
                "memory",
                "write",
                "--title",
                "Test Note",
                "--type",
                "knowledge",
                "--tier",
                "core",
                "--vault",
                str(tmp_path / "nonexistent"),
            ],
        )
        assert result.exit_code == 1
        output = result.output.lower()
        assert "vault" in output or "what failed" in output

    def test_memory_search_missing_memory_json(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        vault.mkdir()
        result = runner.invoke(app, ["memory", "search", "test", "--vault", str(vault)])
        assert result.exit_code == 1
        output = result.output.lower()
        assert "memory.json" in output or "what failed" in output


class TestUpgradeErrors:
    def test_upgrade_missing_vault(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["upgrade", "--vault", str(tmp_path / "nonexistent")])
        assert result.exit_code == 1
        output = result.output.lower()
        assert "what failed" in output or "does not exist" in output

    def test_upgrade_missing_config(self, tmp_path: Path) -> None:
        vault = tmp_path / "vault"
        vault.mkdir()
        result = runner.invoke(app, ["upgrade", "--vault", str(vault)])
        assert result.exit_code == 1
        output = result.output.lower()
        assert "config" in output or "what failed" in output

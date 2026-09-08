"""Tests for cortex doctor command."""

from pathlib import Path

from typer.testing import CliRunner

from cortex.cli.main import app

runner = CliRunner()


class TestDoctor:
    def test_doctor_healthy(self, tmp_path, monkeypatch):
        """Doctor reports healthy when all pieces exist."""
        # Set up a minimal vault
        vault = tmp_path / "vault"
        sync_dir = vault / "_sync"
        sync_dir.mkdir(parents=True)
        (sync_dir / "cortex.yaml").write_text("vault_path: /tmp/vault\n")
        distilled = sync_dir / "encoded"
        distilled.mkdir()
        (distilled / "memory.json").write_text('{"notes": {}}')

        # Set up OpenCode config dir with all assets the validator checks
        oc_config = tmp_path / ".config" / "opencode"
        skills_dir = oc_config / "skills" / "cortex-ai"
        skills_dir.mkdir(parents=True)
        # A loadable OpenCode skill must START with YAML frontmatter.
        (skills_dir / "SKILL.md").write_text(
            "---\nname: cortex-ai\ndescription: test\n---\n\nskill content\n"
        )
        # AGENTS.md in skill dir (checked by OpenCode validator)
        (skills_dir / "AGENTS.md").write_text("# agents\n")
        # tools/cortex.ts in config dir (checked by OpenCode validator)
        tools_dir = oc_config / "tools"
        tools_dir.mkdir(parents=True)
        (tools_dir / "cortex.ts").write_text("export {}\n")
        # package.json with required plugin dep (checked by OpenCode validator)
        (oc_config / "package.json").write_text(
            '{"dependencies": {"@opencode-ai/plugin": "0.1.0"}}\n'
        )

        # Monkeypatch home and paths
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        result = runner.invoke(app, ["doctor", "--vault", str(vault)])
        assert result.exit_code == 0
        assert "HEALTHY" in result.output

    def test_doctor_needs_attention(self, tmp_path, monkeypatch):
        """Doctor reports issues when pieces are missing."""
        vault = tmp_path / "vault"
        vault.mkdir()
        # No _sync/cortex.yaml, no memory.json, no skill

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        result = runner.invoke(app, ["doctor", "--vault", str(vault)])
        assert result.exit_code == 0
        assert "NEEDS ATTENTION" in result.output

    def test_doctor_specific_platform(self, tmp_path, monkeypatch):
        """Doctor with --platform checks only that platform."""
        vault = tmp_path / "vault"
        sync_dir = vault / "_sync"
        sync_dir.mkdir(parents=True)
        (sync_dir / "cortex.yaml").write_text("vault_path: /tmp/vault\n")
        distilled = sync_dir / "encoded"
        distilled.mkdir()
        (distilled / "memory.json").write_text('{"notes": {}}')

        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        result = runner.invoke(app, ["doctor", "--vault", str(vault), "--platform", "opencode"])
        assert result.exit_code == 0
        assert "opencode" in result.output.lower()

    def test_doctor_unknown_platform(self, tmp_path):
        """Doctor with unknown platform exits with error."""
        result = runner.invoke(app, ["doctor", "--platform", "nonexistent"])
        assert result.exit_code == 1
        assert "Unknown platform" in result.output

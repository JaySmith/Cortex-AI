"""Shared fixtures for cortex-ai tests."""

import shutil
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_VAULT = REPO_ROOT / "example-vault"


@pytest.fixture
def vault(tmp_path):
    """Copy example-vault into a temporary directory and return its path."""
    dest = tmp_path / "test-vault"
    shutil.copytree(EXAMPLE_VAULT, dest)
    return dest


@pytest.fixture
def vault_notes(vault):
    """Scan the copied example-vault and return the note list."""
    from cortex.distiller.core import scan_vault
    return scan_vault(vault, skip_dirs={"templates"})

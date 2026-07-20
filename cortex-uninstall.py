#!/usr/bin/env python3
"""
DEPRECATED: Use `cortex uninstall` instead (installed via `uv tool install .` or `pip install -e .`).

This shim will be removed in a future release.
"""

import warnings

warnings.warn(
    "cortex-uninstall.py is deprecated. Use `cortex uninstall` instead.",
    DeprecationWarning,
    stacklevel=2,
)

if __name__ == "__main__":
    from cortex.cli.commands.uninstall import main

    main()

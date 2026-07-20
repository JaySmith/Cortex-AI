#!/usr/bin/env python3
"""
DEPRECATED: Use `cortex import` instead (installed via `uv tool install .` or `pip install -e .`).

This shim will be removed in a future release.
"""

import warnings

warnings.warn(
    "cortex-import.py is deprecated. Use `cortex import` instead.",
    DeprecationWarning,
    stacklevel=2,
)

if __name__ == "__main__":
    from cortex.cli.commands.import_agent import main

    main()

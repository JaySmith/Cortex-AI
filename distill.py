#!/usr/bin/env python3
"""
DEPRECATED: Use `cortex distill` instead (installed via `uv tool install .` or `pip install -e .`).

This shim will be removed in a future release.
"""

import warnings

warnings.warn(
    "distill.py is deprecated. Use `cortex distill` instead.",
    DeprecationWarning,
    stacklevel=2,
)

if __name__ == "__main__":
    from cortex.distiller.core import main

    main()

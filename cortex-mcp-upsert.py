#!/usr/bin/env python3
"""
DEPRECATED: Use `cortex install --upgrade` or `from cortex.mcp.upsert import run` instead.

This shim will be removed in a future release.
"""

import sys
import warnings

warnings.warn(
    "cortex-mcp-upsert.py is deprecated. "
    "Use `cortex install --upgrade` or `from cortex.mcp.upsert import run` instead.",
    DeprecationWarning,
    stacklevel=2,
)

if __name__ == "__main__":
    from cortex.mcp.upsert import main
    sys.exit(main())

#!/usr/bin/env python3
"""
DEPRECATED: Use `from cortex.hub.client import HubClient` instead.

This shim will be removed in a future release.
"""

import sys
import warnings

warnings.warn(
    "hive_client.py is deprecated. Use `from cortex.hub.client import HubClient` instead.",
    DeprecationWarning,
    stacklevel=2,
)

from cortex.hub.client import HubClient, HubConnectionError  # noqa: F401, E402

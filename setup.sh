#!/usr/bin/env bash
#
# DEPRECATED — use `cortex install` instead.
#
# This script is a thin wrapper that:
#   1. Runs `cortex bootstrap` (create venv + install deps)
#   2. Runs `cortex install /path/to/vault`
#
# It will be removed in a future release.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cat <<'EOF'
WARNING: setup.sh is deprecated. Use the cortex CLI instead:

  cortex bootstrap           # create venv + install deps
  cortex install /path/to/vault   # set up config, distiller, skill

EOF

# Try to find the cortex CLI
CORTEX=""
for candidate in \
  "$REPO_ROOT/.venv/bin/cortex" \
  "$(command -v cortex 2>/dev/null || true)"; do
  if [ -n "$candidate" ] && [ -x "$candidate" ]; then
    CORTEX="$candidate"
    break
  fi
done

if [ -z "$CORTEX" ]; then
  echo "cortex CLI not found. Bootstrapping first..."
  python3 -m venv "$REPO_ROOT/.venv"
  "$REPO_ROOT/.venv/bin/python" -m pip install --quiet --upgrade pip
  "$REPO_ROOT/.venv/bin/python" -m pip install --quiet -r "$REPO_ROOT/requirements.txt" 2>/dev/null \
    || "$REPO_ROOT/.venv/bin/python" -m pip install --quiet -e "$REPO_ROOT"
  CORTEX="$REPO_ROOT/.venv/bin/cortex"
fi

# Forward vault arg if provided
VAULT_ARG=""
if [ "${1:-}" != "" ]; then
  VAULT_ARG="$1"
fi

"$CORTEX" bootstrap "$REPO_ROOT"
"$CORTEX" install $VAULT_ARG

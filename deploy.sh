#!/usr/bin/env bash
#
# DEPRECATED — use `cortex install --upgrade` instead.
#
# This script is a thin wrapper around the cortex CLI.
# It will be removed in a future release.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cat <<'EOF'
WARNING: deploy.sh is deprecated. Use the cortex CLI instead:

  cortex install --upgrade /path/to/vault    # upgrade an existing install
  cortex install --upgrade --no-distill      # upgrade without re-distilling

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
  echo "ERROR: cortex CLI not found. Run setup.sh or 'cortex bootstrap' first." >&2
  exit 1
fi

# Forward flags
VAULT="${VAULT_ROOT:-$HOME/Cortex}"
EXTRA_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --apply) ;; # cortex install is always apply (use --dry-run for dry)
    --no-distill) EXTRA_ARGS+=("--no-distill") ;;
    -h|--help)
      echo "Usage: $0 [--apply] [--no-distill]"
      echo ""
      echo "Deprecated. Use instead:"
      echo "  cortex install --upgrade $VAULT"
      exit 0
      ;;
    *) EXTRA_ARGS+=("$arg") ;;
  esac
done

"$CORTEX" install --upgrade "${EXTRA_ARGS[@]}" "$VAULT"

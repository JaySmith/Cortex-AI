#!/usr/bin/env bash
#
# deploy.sh — push this repo's build to a LIVE Cortex install.
#
# setup.sh bootstraps a fresh install (and builds in-repo). deploy.sh is for
# upgrading an EXISTING install whose pieces live in separate places:
#
#   distiller  -> <vault>/_sync/            (distill.py + companions + VERSION/SCHEMA_VERSION)
#   MCP server -> ~/.config/opencode/mcp/cortex/   (build/ + VERSION/SCHEMA_VERSION + package.json)
#   skill      -> ~/.config/opencode/skills/cortex-ai/SKILL.md
#
# It is idempotent, backs every target up first, and (unless --no-distill)
# re-distills the live vault so its schema_version is re-stamped. Dry-run by
# default — pass --apply to actually copy.
#
# Usage:
#   ./deploy.sh                       # dry-run against the default live layout
#   ./deploy.sh --apply               # do it
#   ./deploy.sh --apply --no-distill  # copy files but skip the re-distill
#
# Override any location with env vars (defaults match the current live install):
#   VAULT_ROOT     default: ~/Cortex
#   MCP_HOME       default: ~/.config/opencode/mcp/cortex
#   SKILLS_DIR     default: ~/.config/opencode/skills
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

VAULT_ROOT="${VAULT_ROOT:-$HOME/Cortex}"
MCP_HOME="${MCP_HOME:-$HOME/.config/opencode/mcp/cortex}"
SKILLS_DIR="${SKILLS_DIR:-$HOME/.config/opencode/skills}"

VAULT_ROOT="${VAULT_ROOT/#\~/$HOME}"
MCP_HOME="${MCP_HOME/#\~/$HOME}"
SKILLS_DIR="${SKILLS_DIR/#\~/$HOME}"

DISTILLER_HOME="$VAULT_ROOT/_sync"
SKILL_HOME="$SKILLS_DIR/cortex-ai"
CONFIG_FILE="$DISTILLER_HOME/cortex.yaml"

APPLY=0
DO_DISTILL=1
for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    --no-distill) DO_DISTILL=0 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

REL_VER="$(cat "$REPO_ROOT/VERSION")"
SCHEMA_VER="$(cat "$REPO_ROOT/SCHEMA_VERSION")"
MODE="DRY-RUN (nothing will change)"
[ "$APPLY" = 1 ] && MODE="APPLY"

echo "==> Cortex deploy [$MODE]"
echo "    releasing:  v$REL_VER (schema v$SCHEMA_VER)"
echo "    from repo:  $REPO_ROOT"
echo "    distiller:  $DISTILLER_HOME"
echo "    mcp:        $MCP_HOME"
echo "    skill:      $SKILL_HOME"
echo

# --- Preflight ---------------------------------------------------------------
[ -d "$VAULT_ROOT" ]   || { echo "ERROR: vault not found: $VAULT_ROOT" >&2; exit 1; }
[ -f "$REPO_ROOT/mcp/cortex/build/index.js" ] || {
  echo "ERROR: MCP not built. Run: (cd mcp/cortex && npm run build)" >&2; exit 1; }

# Refuse to deploy older code over a newer live vault (mirror distill's guard).
LIVE_SCHEMA="$(python3 - "$VAULT_ROOT" <<'PY' 2>/dev/null || echo "")
import json, sys
from pathlib import Path
p = Path(sys.argv[1]) / "_sync" / "distilled" / "memory.json"
try:
    print(json.load(open(p))["_meta"].get("schema_version", ""))
except Exception:
    print("")
PY
)"
if [ -n "$LIVE_SCHEMA" ] && [ "$LIVE_SCHEMA" -gt "$SCHEMA_VER" ] 2>/dev/null; then
  echo "ERROR: live vault schema (v$LIVE_SCHEMA) is NEWER than this code (v$SCHEMA_VER)." >&2
  echo "       Refusing to downgrade. Pull the latest repo before deploying." >&2
  exit 1
fi

# --- Backup ------------------------------------------------------------------
STAMP="$(date +%Y%m%d-%H%M%S)"
BK="$VAULT_ROOT/_sync/backups/$STAMP-deploy-$REL_VER"
run() { if [ "$APPLY" = 1 ]; then "$@"; else echo "    [DRY] $*"; fi; }

echo "==> [1/6] Backup live targets -> $BK"
if [ "$APPLY" = 1 ]; then mkdir -p "$BK"; fi
backup() {
  # $1 = source path to snapshot (file or dir)
  local src="$1"
  [ -e "$src" ] || return 0
  local name; name="$(echo "$src" | sed "s#$HOME/##; s#/#_#g")"
  if [ "$APPLY" = 1 ]; then
    cp -pR "$src" "$BK/$name"
  fi
  echo "    backed up $src"
}
backup "$DISTILLER_HOME/distill.py"
backup "$DISTILLER_HOME/VERSION"
backup "$DISTILLER_HOME/SCHEMA_VERSION"
backup "$MCP_HOME/build"
backup "$MCP_HOME/package.json"
backup "$MCP_HOME/VERSION"
backup "$SKILL_HOME/SKILL.md"
backup "$VAULT_ROOT/_sync/distilled/memory.json"
echo

# --- Deploy distiller --------------------------------------------------------
echo "==> [2/6] Distiller -> $DISTILLER_HOME"
for f in distill.py hive_client.py cortex-import.py cortex-uninstall.py gen-portfolio.py \
         cortex-mcp-upsert.py VERSION SCHEMA_VERSION CHANGELOG.md; do
  [ -f "$REPO_ROOT/$f" ] || continue
  run cp -p "$REPO_ROOT/$f" "$DISTILLER_HOME/$f"
done
echo

# --- Deploy MCP --------------------------------------------------------------
echo "==> [3/6] MCP server -> $MCP_HOME"
run mkdir -p "$MCP_HOME/build"
run cp -pR "$REPO_ROOT/mcp/cortex/build/." "$MCP_HOME/build/"
run cp -p "$REPO_ROOT/mcp/cortex/package.json" "$MCP_HOME/package.json"
run cp -p "$REPO_ROOT/VERSION" "$MCP_HOME/VERSION"
run cp -p "$REPO_ROOT/SCHEMA_VERSION" "$MCP_HOME/SCHEMA_VERSION"
if [ "$APPLY" = 1 ]; then
  (cd "$MCP_HOME" && npm install --silent 2>/dev/null) || echo "    WARNING: npm install failed in $MCP_HOME"
fi
echo

# --- Deploy skill ------------------------------------------------------------
# The skill uses <CORTEX_HOME> for the distiller + companions (the vault-resident
# _sync dir). But the MCP lives elsewhere in this split layout, so after the
# <CORTEX_HOME> substitution we rewrite the two MCP path references to $MCP_HOME.
echo "==> [4/6] Skill -> $SKILL_HOME"
if [ "$APPLY" = 1 ]; then
  mkdir -p "$SKILL_HOME"
  sed -e "s#<CORTEX_HOME>#$DISTILLER_HOME#g" \
      -e "s#$DISTILLER_HOME/mcp/cortex#$MCP_HOME#g" \
      "$REPO_ROOT/skills/cortex-ai/SKILL.md" > "$SKILL_HOME/SKILL.md"
  echo "    wrote $SKILL_HOME/SKILL.md (CORTEX_HOME=$DISTILLER_HOME, MCP=$MCP_HOME)"
else
  echo "    [DRY] render skill (CORTEX_HOME=$DISTILLER_HOME, MCP=$MCP_HOME) -> $SKILL_HOME/SKILL.md"
fi
echo

# --- Upsert opencode config -------------------------------------------------
# The helper resolves the active config ($OPENCODE_CONFIG > opencode.jsonc >
# opencode.json > create) and does a comment-preserving surgical edit.
echo "==> [5/6] opencode config"
MEMORY_JSON="$DISTILLER_HOME/distilled/memory.json"
MCP_ENTRY="$MCP_HOME/build/index.js"
PYTHON_UPSERT="$DISTILLER_HOME/.venv/bin/python"
[ -x "$PYTHON_UPSERT" ] || PYTHON_UPSERT="$REPO_ROOT/.venv/bin/python"
[ -x "$PYTHON_UPSERT" ] || PYTHON_UPSERT="python3"
# Use the deployed helper if present (older installs may lack it), else repo copy.
UPSERT_SCRIPT="$DISTILLER_HOME/cortex-mcp-upsert.py"
[ -f "$UPSERT_SCRIPT" ] || UPSERT_SCRIPT="$REPO_ROOT/cortex-mcp-upsert.py"
UPSERT_ARGS=(
  --mcp-entry "$MCP_ENTRY"
  --memory-json "$MEMORY_JSON"
  --vault-root "$VAULT_ROOT"
  --distill-script "$DISTILLER_HOME/distill.py"
  --distill-python "$PYTHON_UPSERT"
)
if [ "$APPLY" = 1 ]; then
  "$PYTHON_UPSERT" "$UPSERT_SCRIPT" "${UPSERT_ARGS[@]}"
else
  "$PYTHON_UPSERT" "$UPSERT_SCRIPT" "${UPSERT_ARGS[@]}" --dry-run
fi
echo

# --- Re-distill --------------------------------------------------------------
echo "==> [6/6] Re-distill live vault"
PYTHON="$DISTILLER_HOME/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="$REPO_ROOT/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="python3"
if [ "$DO_DISTILL" = 0 ]; then
  echo "    skipped (--no-distill)"
elif [ ! -f "$CONFIG_FILE" ]; then
  echo "    WARNING: no config at $CONFIG_FILE — skipping re-distill."
elif [ "$APPLY" = 1 ]; then
  "$PYTHON" "$DISTILLER_HOME/distill.py" --config "$CONFIG_FILE"
else
  echo "    [DRY] $PYTHON $DISTILLER_HOME/distill.py --config $CONFIG_FILE"
fi
echo

# --- Verify ------------------------------------------------------------------
if [ "$APPLY" = 1 ]; then
  echo "==> Verify"
  echo "    distiller VERSION/SCHEMA : $(cat "$DISTILLER_HOME/VERSION") / $(cat "$DISTILLER_HOME/SCHEMA_VERSION")"
  echo "    mcp VERSION/SCHEMA       : $(cat "$MCP_HOME/VERSION") / $(cat "$MCP_HOME/SCHEMA_VERSION")"
  if [ -f "$CONFIG_FILE" ] && [ "$DO_DISTILL" = 1 ]; then
    "$PYTHON" "$DISTILLER_HOME/distill.py" --config "$CONFIG_FILE" --check || true
  fi
  echo
  echo "Deployed v$REL_VER. Restart your agent to load the new MCP build + skill."
else
  echo "Dry-run complete. Re-run with --apply to deploy."
fi

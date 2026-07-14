#!/usr/bin/env bash
#
# setup.sh — one-shot bootstrap for Cortex.
#
# Installs Python deps, builds and deploys the MCP server, wires the distiller
# to the bundled example vault, runs a first distill, installs the cortex-ai
# skill, and upserts the opencode.json MCP entry.
#
# Usage:
#   ./setup.sh                 # interactive: prompts for vault path + skills dir
#   ./setup.sh /path/to/vault  # use this vault, prompt only for skills dir
#
# Env (bypass prompts — useful for scripting/CI):
#   VAULT_ROOT            vault to distill (default: bundled example-vault)
#   OPENCODE_SKILLS_DIR   where to install the cortex-ai skill
#                         (default: ~/.config/opencode/skills)
#
set -euo pipefail

# --- Resolve paths -----------------------------------------------------------
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_VAULT="$REPO_ROOT/example-vault"
DEFAULT_SKILLS="$HOME/.config/opencode/skills"
DEFAULT_MCP="$HOME/.config/opencode/mcp/cortex"

# Only prompt when running interactively (a TTY) and the value wasn't supplied.
prompt_for() {
  # $1 = prompt text, $2 = default value; echoes the chosen value
  local text="$1" def="$2" ans=""
  if [ -t 0 ]; then
    read -r -p "$text [$def]: " ans || true
  fi
  printf '%s' "${ans:-$def}"
}

# Vault: positional arg > VAULT_ROOT env > interactive prompt > default.
if [ "${1:-}" != "" ]; then
  VAULT_ROOT="$1"
elif [ "${VAULT_ROOT:-}" != "" ]; then
  VAULT_ROOT="$VAULT_ROOT"
else
  VAULT_ROOT="$(prompt_for "Vault path" "$DEFAULT_VAULT")"
fi

# Skills dir: OPENCODE_SKILLS_DIR env > interactive prompt > default.
if [ "${OPENCODE_SKILLS_DIR:-}" != "" ]; then
  OPENCODE_SKILLS_DIR="$OPENCODE_SKILLS_DIR"
else
  OPENCODE_SKILLS_DIR="$(prompt_for "opencode skills dir" "$DEFAULT_SKILLS")"
fi

# Expand a leading ~ if the user typed one.
VAULT_ROOT="${VAULT_ROOT/#\~/$HOME}"
OPENCODE_SKILLS_DIR="${OPENCODE_SKILLS_DIR/#\~/$HOME}"

MCP_HOME="$DEFAULT_MCP"

if [ ! -d "$VAULT_ROOT" ]; then
  echo "ERROR: vault path does not exist: $VAULT_ROOT" >&2
  exit 1
fi
VAULT_ROOT="$(cd "$VAULT_ROOT" && pwd)"

DISTILLED_DIR="$VAULT_ROOT/_sync/distilled"
SKILLS_DIR="$DISTILLED_DIR/skills"
MEMORY_JSON="$DISTILLED_DIR/memory.json"
CORE_CONTEXT="$DISTILLED_DIR/opencode/core-context.md"
PROJECTS_DIR="$DISTILLED_DIR/opencode/projects"
CONFIG_FILE="$VAULT_ROOT/_sync/cortex.yaml"

CORTEX_VERSION="$(cat "$REPO_ROOT/VERSION" 2>/dev/null || echo unknown)"
CORTEX_SCHEMA="$(cat "$REPO_ROOT/SCHEMA_VERSION" 2>/dev/null || echo 1)"
echo "==> Cortex setup (v$CORTEX_VERSION, schema v$CORTEX_SCHEMA)"
echo "    repo:  $REPO_ROOT"
echo "    vault: $VAULT_ROOT"
echo

# Install manifest — records everything this run creates/modifies so
# cortex-uninstall.py can cleanly revert. One manifest per setup run.
STAMP="$(date +%Y%m%d-%H%M%S)"
MANIFEST_DIR="$VAULT_ROOT/_sync/backups/$STAMP-setup"
MANIFEST="$MANIFEST_DIR/manifest.json"
mkdir -p "$MANIFEST_DIR"

# Append a JSON action line to a temp file; assembled into manifest at the end.
MANIFEST_ACTIONS="$MANIFEST_DIR/.actions.jsonl"
: > "$MANIFEST_ACTIONS"
record_action() {
  # $1=op (created|modified|backup)  $2=path  $3=saved_as (optional, relative)
  local op="$1" path="$2" saved="${3:-}"
  if [ -n "$saved" ]; then
    printf '{"op":"%s","path":"%s","saved_as":"%s"}\n' "$op" "$path" "$saved" >> "$MANIFEST_ACTIONS"
  else
    printf '{"op":"%s","path":"%s"}\n' "$op" "$path" >> "$MANIFEST_ACTIONS"
  fi
}

# --- 1. Python environment ---------------------------------------------------
echo "==> [1/7] Python environment"
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 not found on PATH." >&2
  exit 1
fi
if [ ! -d "$REPO_ROOT/.venv" ]; then
  python3 -m venv "$REPO_ROOT/.venv"
fi
PYTHON="$REPO_ROOT/.venv/bin/python"
"$PYTHON" -m pip install --quiet --upgrade pip
"$PYTHON" -m pip install --quiet -r "$REPO_ROOT/requirements.txt"
echo "    deps installed into .venv"
echo

# --- 2. Build the MCP server -------------------------------------------------
echo "==> [2/7] MCP server build"
if ! command -v npm >/dev/null 2>&1; then
  echo "WARNING: npm not found — skipping MCP build. Install Node 18+ and run:"
  echo "         (cd mcp/cortex && npm install && npm run build)"
else
  (cd "$REPO_ROOT/mcp/cortex" && npm install --silent && npm run build --silent)
  echo "    built mcp/cortex/build/index.js"
fi
echo

# --- 3. Deploy MCP server to ~/.config/opencode/mcp/cortex/ ------------------
echo "==> [3/7] Deploy MCP server"
if [ ! -d "$REPO_ROOT/mcp/cortex/build" ]; then
  echo "    WARNING: MCP not built — skipping deploy"
elif ! command -v npm >/dev/null 2>&1; then
  echo "    WARNING: npm not found — skipping MCP deploy"
else
  mkdir -p "$MCP_HOME/build"
  cp -p "$REPO_ROOT/mcp/cortex/build/index.js" "$MCP_HOME/build/index.js"
  cp -p "$REPO_ROOT/mcp/cortex/build/vault.js" "$MCP_HOME/build/vault.js" 2>/dev/null || true
  cp -p "$REPO_ROOT/mcp/cortex/build/hub-client.js" "$MCP_HOME/build/hub-client.js" 2>/dev/null || true
  cp -p "$REPO_ROOT/mcp/cortex/package.json" "$MCP_HOME/package.json"
  cp -p "$REPO_ROOT/VERSION" "$MCP_HOME/VERSION"
  cp -p "$REPO_ROOT/SCHEMA_VERSION" "$MCP_HOME/SCHEMA_VERSION"
  (cd "$MCP_HOME" && npm install --silent 2>/dev/null) || echo "    WARNING: npm install failed in $MCP_HOME"
  echo "    deployed MCP -> $MCP_HOME"
fi
echo

# --- 3. Generate cortex.yaml (only if missing) -------------------------------
echo "==> [4/7] Config"
mkdir -p "$(dirname "$CONFIG_FILE")"
if [ -f "$CONFIG_FILE" ]; then
  echo "    $CONFIG_FILE already exists — leaving it untouched"
else
  cat > "$CONFIG_FILE" <<YAML
# Cortex — generated by setup.sh
# Points at: $VAULT_ROOT
# schema_version is informational here; the authoritative on-disk schema is
# stamped into _sync/distilled/memory.json by the distiller.
schema_version: $CORTEX_SCHEMA
vault_path: "$VAULT_ROOT"

eager_tiers:
  - core

skip_dirs:
  - templates
  - archive

exclude_tags:
  - draft
  - archived

vault_only_types:
  - session
  - log

targets:
  core_context:
    enabled: true
    type: core-context
    output_file: "$CORE_CONTEXT"

  skills:
    enabled: true
    type: skill-embed
    skills_dir: "$SKILLS_DIR"
    embed_filename: "reference.md"

  projects:
    enabled: true
    type: project-context
    output_dir: "$PROJECTS_DIR"

  python-agents:
    enabled: true
    type: json
    output_file: "$MEMORY_JSON"
    include_types:
      - knowledge
      - entity

strip_wiki_links: true
YAML
  echo "    wrote $CONFIG_FILE"
  record_action created "$CONFIG_FILE"
fi
echo

# --- 4. Ensure skill target dirs exist, then distill -------------------------
echo "==> [5/7] First distill"
# The distiller only writes skill reference.md into dirs that already exist.
# Pre-create any skill dirs referenced by skill:<name> notes in the vault.
"$PYTHON" - "$VAULT_ROOT" "$SKILLS_DIR" <<'PY'
import re, sys
from pathlib import Path
vault, skills_dir = Path(sys.argv[1]), Path(sys.argv[2])
skills = set()
for md in vault.rglob("*.md"):
    if any(p.startswith(('.', '_')) for p in md.relative_to(vault).parts):
        continue
    m = re.search(r'^tier:\s*skill:(\S+)', md.read_text(encoding='utf-8'), re.M)
    if m:
        skills.add(m.group(1))
for s in sorted(skills):
    (skills_dir / s).mkdir(parents=True, exist_ok=True)
    print(f"    ensured skill dir: {s}")
PY
"$PYTHON" "$REPO_ROOT/distill.py" --config "$CONFIG_FILE"
echo

# --- 5. Install the cortex-ai skill + upsert opencode.json -------------------
echo "==> [6/7] Skill + opencode.json"
SKILL_SRC="$REPO_ROOT/skills/cortex-ai/SKILL.md"
if [ -f "$SKILL_SRC" ]; then
  SKILL_DEST_DIR="$OPENCODE_SKILLS_DIR/cortex-ai"
  SKILL_DEST="$SKILL_DEST_DIR/SKILL.md"
  # Track whether we're overwriting an existing skill (so uninstall knows to
  # restore vs. delete). If it exists, back it up first.
  if [ -f "$SKILL_DEST" ]; then
    cp -p "$SKILL_DEST" "$MANIFEST_DIR/cortex-ai.SKILL.md.bak"
    record_action modified "$SKILL_DEST" "cortex-ai.SKILL.md.bak"
  else
    record_action created "$SKILL_DEST"
  fi
  mkdir -p "$SKILL_DEST_DIR"
  # Only <CORTEX_HOME> is baked in. Vault paths are resolved at runtime by the
  # skill via `distill.py --show-config`, so no <VAULT_ROOT> substitution here.
  sed -e "s#<CORTEX_HOME>#$REPO_ROOT#g" \
      "$SKILL_SRC" > "$SKILL_DEST"
  echo "    installed skill -> $SKILL_DEST"
else
  echo "    WARNING: skill source not found at $SKILL_SRC — skipping"
fi

# Upsert cortex MCP entry in opencode.json
OPENCODE_JSON="$HOME/.config/opencode/opencode.json"
if [ -f "$OPENCODE_JSON" ]; then
  MCP_ENTRY="$MCP_HOME/build/index.js"
  python3 - "$OPENCODE_JSON" "$MCP_ENTRY" "$MEMORY_JSON" "$VAULT_ROOT" "$REPO_ROOT/distill.py" "$PYTHON" <<'PY'
import json, sys
from pathlib import Path
opencode_json, mcp_entry, memory_json, vault_root, distill_script, distill_python = sys.argv[1:7]
p = Path(opencode_json)
cfg = json.loads(p.read_text())
mcp = cfg.setdefault("mcp", {})
mcp["cortex"] = {
    "type": "local",
    "command": ["node", mcp_entry],
    "environment": {
        "MEMORY_JSON": memory_json,
        "VAULT_ROOT": vault_root,
        "DISTILL_SCRIPT": distill_script,
        "DISTILL_PYTHON": distill_python,
    },
    "enabled": True,
}
p.write_text(json.dumps(cfg, indent=2) + "\n")
# Validate: opencode MCP config must use "environment", not "env"
if "env" in mcp.get("cortex", {}):
    print(f"    ERROR: cortex MCP entry uses deprecated 'env' key — must be 'environment'")
    sys.exit(1)
print(f"    upserted cortex MCP entry in {opencode_json}")
PY
else
  echo "    WARNING: $OPENCODE_JSON not found — skipping MCP config"
fi
echo

# --- Finalize install manifest -----------------------------------------------
# Assemble the recorded actions into a manifest.json that cortex-uninstall.py
# reads. If nothing was recorded (e.g. re-run with existing config/skill), drop
# the empty backup dir to avoid clutter.
if [ -s "$MANIFEST_ACTIONS" ]; then
  "$PYTHON" - "$MANIFEST" "$MANIFEST_ACTIONS" "$CORTEX_VERSION" "$CORTEX_SCHEMA" \
    "$VAULT_ROOT" "$REPO_ROOT" <<'PY'
import json, sys
from datetime import datetime
manifest, actions_file, ver, schema, vault, repo = sys.argv[1:7]
actions = []
with open(actions_file) as f:
    for line in f:
        line = line.strip()
        if line:
            actions.append(json.loads(line))
doc = {
    "cortex_version": ver,
    "schema_version": int(schema),
    "created": datetime.now().isoformat(),
    "vault_root": vault,
    "repo_root": repo,
    "actions": actions,
}
with open(manifest, "w") as f:
    json.dump(doc, f, indent=2)
print(f"    install manifest -> {manifest}")
PY
  rm -f "$MANIFEST_ACTIONS"
else
  rm -f "$MANIFEST_ACTIONS"
  rmdir "$MANIFEST_DIR" 2>/dev/null || true
fi
echo

# --- 6. Done ------------------------------------------------------------------
echo "==> [7/7] Done"
echo
echo "Distilled output is in: $DISTILLED_DIR"
echo "MCP server deployed to: $MCP_HOME"
echo "opencode.json updated:  $OPENCODE_JSON"
echo
echo "Optional — import your existing agent's config/memory into the vault:"
echo "  $PYTHON $REPO_ROOT/cortex-import.py --vault \"$VAULT_ROOT\" --dry-run"
echo "  (backs up what it reads, imports AGENTS.md/CLAUDE.md/opencode instructions/~/.claude/memory)"
echo
echo "Health / version check:"
echo "  $PYTHON $REPO_ROOT/distill.py --config \"$CONFIG_FILE\" --check"
echo
echo "Changed your mind? Revert everything Cortex added (keeps your notes):"
echo "  $PYTHON $REPO_ROOT/cortex-uninstall.py --vault \"$VAULT_ROOT\" --latest        # dry-run"
echo "  $PYTHON $REPO_ROOT/cortex-uninstall.py --vault \"$VAULT_ROOT\" --latest --apply"

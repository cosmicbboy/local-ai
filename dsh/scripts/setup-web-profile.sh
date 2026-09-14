#!/bin/bash
# setup-web-profile.sh — one-time bootstrap of the dsh web profile + provider settings.
# Run this BEFORE install.sh on a fresh machine. Safe to re-run.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_HOME="$HOME"
DSH_HOME="$USER_HOME/.dsh"

log() { printf '\n==> %s\n' "$*"; }

# ---------------------------------------------------------------------------
log "1. Installing the dsh CLI (if missing)"
if ! command -v dsh >/dev/null 2>&1; then
    npm install -g @deepseek-ai/dsh
fi
DSH_BIN="$(command -v dsh)"
log "   dsh: $DSH_BIN ($(dsh --version 2>/dev/null || echo '?'))"

# ---------------------------------------------------------------------------
log "2. Creating ~/.dsh home and the 'web' profile"
mkdir -p "$DSH_HOME/profiles"
WEB_PROFILE="$DSH_HOME/profiles/web"
mkdir -p "$WEB_PROFILE"
cp "$REPO_DIR/dsh/profile/web/package.json"        "$WEB_PROFILE/"
cp "$REPO_DIR/dsh/profile/web/cordis.yml"          "$WEB_PROFILE/"
cp "$REPO_DIR/dsh/profile/web/cordis.patch.yml"    "$WEB_PROFILE/"
cp "$REPO_DIR/dsh/profile/web/pnpm-workspace.yaml" "$WEB_PROFILE/"

# ---------------------------------------------------------------------------
log "3. Installing provider settings -> ~/.dsh/settings.yaml (backing up any existing)"
if [ -f "$DSH_HOME/settings.yaml" ]; then
    cp "$DSH_HOME/settings.yaml" "$DSH_HOME/settings.yaml.bak.$(date +%s)"
fi
cp "$REPO_DIR/dsh/config/settings.yaml" "$DSH_HOME/settings.yaml"

# ---------------------------------------------------------------------------
log "4. Credentials (~/.dsh/.credentials.yaml)"
if [ ! -f "$DSH_HOME/.credentials.yaml" ]; then
    cp "$REPO_DIR/dsh/config/credentials.example.yaml" "$DSH_HOME/.credentials.yaml"
    chmod 600 "$DSH_HOME/.credentials.yaml"
    echo "   Created .credentials.yaml from template — EDIT IT and fill in real secrets."
else
    echo "   Found existing .credentials.yaml; leaving it untouched."
fi

# ---------------------------------------------------------------------------
log "5. Verifying the env var is available to dsh"
if [ -z "${QWEN_TOKEN_PLAN_API_KEY:-}" ]; then
    echo "   NOTE: QWEN_TOKEN_PLAN_API_KEY is not exported. Export it (or put it in"
    echo "   ~/.dsh/.credentials.yaml under refs:) before relying on cloud models."
else
    echo "   QWEN_TOKEN_PLAN_API_KEY is set (${#QWEN_TOKEN_PLAN_API_KEY} chars)."
fi

echo
echo "Profile ready. Now run ./install.sh to install the LaunchAgent + menu bar app."

#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="${APP_NAME:-race-reminder-bot}"
REPO_DIR="${REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
BRANCH="${BRANCH:-main}"
PYTHON_BIN="${PYTHON_BIN:-python3.14}"
LOG_DIR="$REPO_DIR/logs"
LOG_FILE="$LOG_DIR/deploy_restart.log"

mkdir -p "$LOG_DIR"
exec >>"$LOG_FILE" 2>&1

printf '\n[%s] deploy restart started\n' "$(date -Is)"
cd "$REPO_DIR"

git fetch origin "$BRANCH"
git pull --ff-only origin "$BRANCH"

if [ ! -x .venv/bin/python ]; then
  "$PYTHON_BIN" -m venv .venv
fi

.venv/bin/python -m pip install -r requirements.txt
.venv/bin/pytest -q

mkdir -p data logs
pm2 startOrReload ecosystem.config.cjs --only "$APP_NAME" --update-env
pm2 save

printf '[%s] deploy restart finished\n' "$(date -Is)"

#!/usr/bin/env bash
set -Eeuo pipefail

APP_NAME="${APP_NAME:-race-reminder-bot}"
REPO_DIR="${REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
BRANCH="${BRANCH:-main}"
INTERVAL="${DEPLOY_WATCH_INTERVAL:-60}"
LOG_DIR="$REPO_DIR/logs"
LOG_FILE="$LOG_DIR/deploy_watch.log"

mkdir -p "$LOG_DIR"
exec >>"$LOG_FILE" 2>&1

cd "$REPO_DIR"
printf '[%s] deploy watch started repo=%s branch=%s interval=%ss\n' "$(date -Is)" "$REPO_DIR" "$BRANCH" "$INTERVAL"

while true; do
  if git fetch origin "$BRANCH"; then
    local_sha="$(git rev-parse HEAD)"
    remote_sha="$(git rev-parse "origin/$BRANCH")"
    if [ "$local_sha" != "$remote_sha" ]; then
      printf '[%s] new commit detected %s -> %s\n' "$(date -Is)" "$local_sha" "$remote_sha"
      APP_NAME="$APP_NAME" REPO_DIR="$REPO_DIR" BRANCH="$BRANCH" "$REPO_DIR/scripts/deploy_restart.sh" || true
    fi
  else
    printf '[%s] git fetch failed\n' "$(date -Is)"
  fi
  sleep "$INTERVAL"
done

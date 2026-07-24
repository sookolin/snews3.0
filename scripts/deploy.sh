#!/usr/bin/env bash
#
# deploy.sh — pull latest code from GitHub and (re)deploy on a Linux VPS.
#
# Intended to be run on the server (manually or from CI over SSH). Idempotent
# and safe to re-run. Requires: git, docker, docker compose.
#
set -euo pipefail

APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
BRANCH="${DEPLOY_BRANCH:-main}"
COMPOSE="docker compose"

log() { echo -e "\033[1;34m[deploy]\033[0m $*"; }

cd "$APP_DIR"

log "Deploying from $APP_DIR (branch: $BRANCH)"

if [ ! -f .env ]; then
    log "ERROR: .env not found. Copy .env.example to .env and fill in secrets."
    exit 1
fi

log "Fetching latest code..."
git fetch --all --prune
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"

log "Building images..."
$COMPOSE build

log "Applying database migrations..."
$COMPOSE run --rm backend migrate

log "Restarting services..."
$COMPOSE up -d --remove-orphans

log "Pruning old images..."
docker image prune -f >/dev/null 2>&1 || true

log "Waiting for backend health..."
for i in $(seq 1 30); do
    if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
        log "Backend is healthy."
        break
    fi
    sleep 2
done

log "Deploy complete."
$COMPOSE ps

#!/bin/bash
# Next strategy rollout helper (no-docker systemd environment)
# - Pull latest code
# - Restart trading services
# - Validate service health
# - Trigger surge alert smoke task

set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/home/ubuntu/autotraderx}"
BACKEND_DIR="$PROJECT_DIR/backend"
LOG_FILE="$PROJECT_DIR/logs/next_strategy.log"

mkdir -p "$(dirname "$LOG_FILE")"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "ERROR: missing command: $1"
    exit 1
  fi
}

require_cmd git
require_cmd systemctl

if [[ ! -d "$PROJECT_DIR/.git" ]]; then
  log "ERROR: project dir not found: $PROJECT_DIR"
  exit 1
fi

cd "$PROJECT_DIR"

log "Fetching latest code"
git fetch origin master
CURRENT_HASH="$(git rev-parse HEAD)"
REMOTE_HASH="$(git rev-parse origin/master)"

if [[ "$CURRENT_HASH" != "$REMOTE_HASH" ]]; then
  log "Updating code: $CURRENT_HASH -> $REMOTE_HASH"
  git pull origin master
else
  log "Code already up to date"
fi

if [[ -f "$BACKEND_DIR/requirements.txt" ]]; then
  log "Ensuring backend dependencies"
  pushd "$BACKEND_DIR" >/dev/null
  source venv/bin/activate
  pip install -r requirements.txt --quiet
  deactivate
  popd >/dev/null
fi

log "Restarting services"
sudo systemctl restart autotrader-backend
sudo systemctl restart autotrader-worker
sudo systemctl restart autotrader-scheduler
sudo systemctl restart autotrader-frontend

sleep 3

check_service() {
  local svc="$1"
  if systemctl is-active --quiet "$svc"; then
    log "OK: $svc"
  else
    log "FAIL: $svc"
    sudo systemctl status "$svc" --no-pager | tail -n 30 | tee -a "$LOG_FILE"
    exit 1
  fi
}

check_service autotrader-backend
check_service autotrader-worker
check_service autotrader-scheduler
check_service autotrader-frontend

log "Triggering surge alert smoke task"
pushd "$BACKEND_DIR" >/dev/null
source venv/bin/activate
celery -A app.celery_app call app.celery_app.run_surge_alert_loop >/tmp/surge_alert_task.out
cat /tmp/surge_alert_task.out | tail -n 2 | tee -a "$LOG_FILE"
deactivate
popd >/dev/null

log "Recent scheduler logs"
sudo journalctl -u autotrader-scheduler -n 40 --no-pager | tee -a "$LOG_FILE"

log "Next strategy rollout completed"

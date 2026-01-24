#!/bin/bash
# 자동 배포 스크립트 - git pull 후 서비스 재시작
# 사용법: ./auto_deploy.sh
# cron에 등록하여 주기적 실행 또는 webhook으로 호출

set -e

PROJECT_DIR="/home/ubuntu/autotraderx"
LOG_FILE="/home/ubuntu/autotraderx/logs/deploy.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

cd "$PROJECT_DIR"

# 현재 커밋 해시
OLD_HASH=$(git rev-parse HEAD)

# 최신 코드 Pull
log "Pulling latest code..."
git fetch origin master
NEW_HASH=$(git rev-parse origin/master)

# 변경사항이 없으면 종료
if [ "$OLD_HASH" == "$NEW_HASH" ]; then
    log "No changes detected. Skipping deployment."
    exit 0
fi

log "Changes detected: $OLD_HASH -> $NEW_HASH"
git pull origin master

# Backend 의존성 업데이트 (requirements.txt 변경 시)
if git diff --name-only "$OLD_HASH" "$NEW_HASH" | grep -q "backend/requirements.txt"; then
    log "Updating backend dependencies..."
    cd "$PROJECT_DIR/backend"
    source venv/bin/activate
    pip install -r requirements.txt --quiet
    deactivate
fi

# Frontend 의존성 업데이트 (package.json 변경 시)
if git diff --name-only "$OLD_HASH" "$NEW_HASH" | grep -q "frontend/package.json"; then
    log "Updating frontend dependencies..."
    cd "$PROJECT_DIR/frontend"
    npm install --legacy-peer-deps
    npm run build
fi

# Frontend 빌드 (소스 변경 시)
if git diff --name-only "$OLD_HASH" "$NEW_HASH" | grep -q "frontend/src/"; then
    log "Rebuilding frontend..."
    cd "$PROJECT_DIR/frontend"
    npm run build
fi

# 서비스 재시작
log "Restarting services..."
sudo systemctl restart autotrader-backend
sudo systemctl restart autotrader-worker
sudo systemctl restart autotrader-scheduler
sudo systemctl restart autotrader-frontend

# 상태 확인
sleep 3
log "Checking service status..."
systemctl is-active autotrader-backend && log "✅ Backend: OK" || log "❌ Backend: FAILED"
systemctl is-active autotrader-worker && log "✅ Worker: OK" || log "❌ Worker: FAILED"
systemctl is-active autotrader-scheduler && log "✅ Scheduler: OK" || log "❌ Scheduler: FAILED"
systemctl is-active autotrader-frontend && log "✅ Frontend: OK" || log "❌ Frontend: FAILED"

log "Deployment completed successfully!"

#!/bin/bash
# Oracle Cloud 서버 초기 설정 스크립트 (Docker 없이)
# 사용법: ./setup_no_docker.sh

set -e

echo "=== AutoTrader 서버 설정 (No Docker) ==="

# 1. 시스템 업데이트
echo ">>> 시스템 업데이트..."
sudo apt update && sudo apt upgrade -y

# 2. 필수 패키지 설치
echo ">>> 필수 패키지 설치..."
sudo apt install -y python3.11 python3.11-venv python3-pip \
    postgresql postgresql-contrib redis-server \
    git curl build-essential libpq-dev

# 3. Node.js 설치 (NVM 사용)
echo ">>> Node.js 설치..."
if [ ! -d "$HOME/.nvm" ]; then
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.0/install.sh | bash
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
    nvm install 20
    nvm use 20
fi

# 4. PostgreSQL 설정
echo ">>> PostgreSQL 설정..."
sudo systemctl start postgresql
sudo systemctl enable postgresql

# DB 및 사용자 생성 (이미 존재하면 무시)
sudo -u postgres psql -c "CREATE USER autotrader WITH PASSWORD 'autotrader';" 2>/dev/null || true
sudo -u postgres psql -c "CREATE DATABASE autotrader OWNER autotrader;" 2>/dev/null || true
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE autotrader TO autotrader;" 2>/dev/null || true

# 5. Redis 시작
echo ">>> Redis 시작..."
sudo systemctl start redis-server
sudo systemctl enable redis-server

# 6. 프로젝트 클론 또는 업데이트
PROJECT_DIR="$HOME/autotraderx"
if [ -d "$PROJECT_DIR" ]; then
    echo ">>> 기존 프로젝트 업데이트..."
    cd "$PROJECT_DIR"
    git pull origin master
else
    echo ">>> 프로젝트 클론..."
    git clone https://github.com/oksk1111/autotraderx.git "$PROJECT_DIR"
    cd "$PROJECT_DIR"
fi

# 7. Backend 가상환경 및 의존성 설치
echo ">>> Backend 설정..."
cd "$PROJECT_DIR/backend"
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# 8. Frontend 빌드
echo ">>> Frontend 빌드..."
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
cd "$PROJECT_DIR/frontend"
npm install --legacy-peer-deps
npm run build

# 9. 환경변수 파일 확인
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo ">>> .env 파일 생성..."
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env" 2>/dev/null || touch "$PROJECT_DIR/.env"
    echo "⚠️  .env 파일을 수정해주세요 (Upbit API 키 등)"
fi

# 10. systemd 서비스 설치
echo ">>> systemd 서비스 설치..."
sudo cp "$PROJECT_DIR/deploy/systemd/"*.service /etc/systemd/system/
sudo systemctl daemon-reload

# 11. 서비스 활성화 및 시작
echo ">>> 서비스 시작..."
sudo systemctl enable autotrader-backend autotrader-worker autotrader-scheduler autotrader-frontend
sudo systemctl start autotrader-backend autotrader-worker autotrader-scheduler autotrader-frontend

# 12. 방화벽 설정
echo ">>> 방화벽 설정..."
sudo ufw allow 8000/tcp  # Backend API
sudo ufw allow 4173/tcp  # Frontend

# 13. 자동 배포 cron 설정
echo ">>> 자동 배포 cron 설정..."
chmod +x "$PROJECT_DIR/deploy/auto_deploy.sh"
mkdir -p "$PROJECT_DIR/logs"

# cron에 1분마다 자동 배포 체크 등록
(crontab -l 2>/dev/null | grep -v "auto_deploy.sh"; echo "* * * * * $PROJECT_DIR/deploy/auto_deploy.sh >> $PROJECT_DIR/logs/cron.log 2>&1") | crontab -

echo ""
echo "=== 설정 완료 ==="
echo "Frontend: http://$(curl -s ifconfig.me):4173"
echo "Backend API: http://$(curl -s ifconfig.me):8000/docs"
echo ""
echo "⚠️  .env 파일을 수정한 후 서비스를 재시작하세요:"
echo "   nano ~/autotraderx/.env"
echo "   sudo systemctl restart autotrader-backend autotrader-worker autotrader-scheduler"

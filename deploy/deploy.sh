#!/bin/bash

# 서비스 배포/업데이트 스크립트
# 실행 방법: ./deploy.sh

set -e

PROJECT_DIR="$HOME/autotraderx"
REPO_URL="https://github.com/oksk1111/autotraderx.git" # 실제 레포 주소로 변경 필요

# 1. 프로젝트 디렉토리 확인 및 클론
if [ -d "$PROJECT_DIR" ]; then
    echo "=== 프로젝트 디렉토리로 이동 및 최신 코드 Pull ==="
    cd "$PROJECT_DIR"
    git pull origin master
else
    echo "=== 프로젝트 클론 ==="
    git clone "$REPO_URL" "$PROJECT_DIR"
    cd "$PROJECT_DIR"
fi

# 2. 환경 변수 파일 확인
if [ ! -f ".env" ]; then
    echo "경고: .env 파일이 없습니다. .env.example을 복사하거나 직접 생성해야 합니다."
    # exit 1 # 실제 운영 시에는 주석 해제 권장
fi

# 3. Docker Compose 빌드 및 실행 (프로덕션 설정 적용)
echo "=== Docker Compose 빌드 및 실행 ==="
# docker-compose.prod.yml이 있다면 -f docker-compose.yml -f docker-compose.prod.yml 사용
# 현재는 기본 파일 사용
docker compose up -d --build

echo "=== 배포 완료 ==="
docker compose ps

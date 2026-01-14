#!/bin/bash

# 서버 초기 설정 스크립트 (Ubuntu 22.04+ 기준)
# 실행 방법: chmod +x setup_server.sh && ./setup_server.sh

set -e

echo "=== 서버 업데이트 및 필수 패키지 설치 ==="
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release git ufw

echo "=== Docker 공식 GPG 키 추가 ==="
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

echo "=== Docker 저장소 설정 ==="
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

echo "=== Docker Engine 설치 ==="
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

echo "=== 현재 사용자를 docker 그룹에 추가 (재로그인 필요) ==="
sudo usermod -aG docker $USER

echo "=== 방화벽 설정 (UFW) ==="
# SSH, HTTP, HTTPS 허용
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
# Docker Swarm 등을 쓰지 않는다면 기본적으로 닫혀있음.
# DB(5432), Redis(6379)는 외부 오픈 금지 (Docker Network로만 통신)

echo "=== 방화벽 활성화 ==="
echo "y" | sudo ufw enable

echo "=== 설치 완료 ==="
echo "Docker 버전:"
docker --version
echo "Docker Compose 버전:"
docker compose version

echo "로그아웃 후 다시 로그인하거나 'newgrp docker' 명령어를 실행하여 그룹 변경사항을 적용하세요."

# Oracle Cloud 배포 가이드 (Docker 없이 - 권장)

이 가이드는 Docker 없이 systemd 서비스로 직접 실행하는 방법을 설명합니다.

## 장점
- ✅ **자동 배포**: git push만 하면 1분 내 자동 반영
- ✅ **리소스 절약**: Docker 오버헤드 없음 (Oracle Cloud 무료 티어에 적합)
- ✅ **빠른 배포**: 이미지 빌드 불필요 (수 초 내 완료)
- ✅ **간편한 로그 확인**: `journalctl`로 실시간 로그 확인

## 1단계: 서버 접속

```bash
ssh -i ssh-key-2026-01-14.key ubuntu@158.180.71.84
```

## 2단계: 초기 설정 (최초 1회)

```bash
# 프로젝트 클론
git clone https://github.com/oksk1111/autotraderx.git ~/autotraderx
cd ~/autotraderx/deploy

# 설정 스크립트 실행
chmod +x setup_no_docker.sh
./setup_no_docker.sh
```

## 3단계: 환경변수 설정

```bash
nano ~/autotraderx/.env
```

필수 설정:
```env
# Database (로컬 PostgreSQL)
DATABASE_URL=postgresql://autotrader:autotrader@localhost:5432/autotrader
POSTGRES_HOST=localhost

# Redis (로컬)
REDIS_URL=redis://localhost:6379/0
REDIS_HOST=localhost

# Upbit API (필수!)
UPBIT_ACCESS_KEY=your_access_key
UPBIT_SECRET_KEY=your_secret_key

# 기타
ENVIRONMENT=production
DEBUG=false
```

## 4단계: 서비스 재시작

```bash
sudo systemctl restart autotrader-backend autotrader-worker autotrader-scheduler autotrader-frontend
```

## 자동 배포 동작 방식 (GitHub Actions)

1. **git push** → GitHub에 코드 푸시 (master/main 브랜치)
2. **GitHub Actions** → `Run Deploy` 워크플로우 실행 (`.github/workflows/deploy.yml`)
3. **SSH 접속 & 배포** → 서버에 접속하여 git pull 및 서비스 재시작
4. **Health Check** → Systemd 로그 확인 및 URL 접속 테스트 (`/api/health`)

GitHub Actions 로그 확인: [Actions 탭](https://github.com/oksk1111/autotraderx/actions)

## 서비스 관리 명령어

```bash
# 상태 확인
sudo systemctl status autotrader-backend
sudo systemctl status autotrader-worker
sudo systemctl status autotrader-scheduler
sudo systemctl status autotrader-frontend

# 로그 확인 (실시간)
sudo journalctl -u autotrader-backend -f
sudo journalctl -u autotrader-worker -f

# 전체 재시작
sudo systemctl restart autotrader-backend autotrader-worker autotrader-scheduler autotrader-frontend

# 서비스 중지
sudo systemctl stop autotrader-backend autotrader-worker autotrader-scheduler autotrader-frontend
```

## Docker에서 마이그레이션

기존 Docker 환경에서 전환하려면:

```bash
# 1. Docker 컨테이너 중지
cd ~/autotraderx
docker compose down

# 2. 새 설정 스크립트 실행
cd deploy
./setup_no_docker.sh

# 3. .env 파일 수정 (DB/Redis를 localhost로 변경)
nano ~/autotraderx/.env

# 4. 서비스 시작
sudo systemctl start autotrader-backend autotrader-worker autotrader-scheduler autotrader-frontend
```

## 접속 URL

- **Frontend**: http://158.180.71.84:4173
- **Backend API**: http://158.180.71.84:8000/docs

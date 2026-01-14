#!/bin/bash
set -e

# [Debug] 스크립트 실행 시작 알림
echo "Starting backend entrypoint script..."

# 라이브러리/모델 의존성 확인 (LightGBM 등)
echo "Checking system dependencies..."
python -c "import lightgbm; print('LightGBM import successful')" || { echo "Failed to import LightGBM. Please rebuild docker image."; exit 1; }

# DB 연결 대기 (실제 인증 포함)
echo "Waiting for PostgreSQL to be ready..."
timeout=60
counter=0
until python -c "
import sys
import psycopg2
import os
try:
    psycopg2.connect(
        dbname=os.environ.get('POSTGRES_DB', 'autotrader'),
        user=os.environ.get('POSTGRES_USER', 'autotrader'),
        password=os.environ.get('POSTGRES_PASSWORD', 'autotrader'),
        host=os.environ.get('POSTGRES_HOST', 'postgres'),
        port=5432
    )
    print('DB Connection Successful')
except Exception as e:
    print(e)
    sys.exit(1)
"; do
  echo "PostgreSQL is unavailable - sleeping... ($counter/$timeout)"
  sleep 2
  counter=$((counter+1))
  if [ $counter -ge $timeout ]; then
      echo "Timeout waiting for PostgreSQL"
      exit 1
  fi
done

echo "PostgreSQL is up - executing migrations"

# DB 마이그레이션 실행 (테이블 생성 및 업데이트)
echo "Running database migrations..."
alembic upgrade head || { echo "Alembic migration failed"; exit 1; }

# 서버 실행
echo "Starting server..."
# 모델 디렉토리 확인
ls -la /app/models/ || echo "/app/models directory not found"

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

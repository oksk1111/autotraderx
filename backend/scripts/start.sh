#!/bin/bash
set -e

# DB 준비 대기 (간단한 루프)
echo "Waiting for PostgreSQL to be ready..."
until python -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); s.connect(('postgres', 5432))" 2>/dev/null; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 2
done
echo "PostgreSQL is up - executing migrations"

# DB 마이그레이션 실행 (테이블 생성 및 업데이트)
echo "Running database migrations..."
alembic upgrade head

# 서버 실행
echo "Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

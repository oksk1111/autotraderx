#!/bin/bash
set -e

# DB 마이그레이션 실행 (테이블 생성 및 업데이트)
echo "Running database migrations..."
alembic upgrade head

# 서버 실행
echo "Starting server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

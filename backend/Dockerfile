FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y build-essential libgomp1 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY scripts ./scripts
COPY data ./data
COPY models ./models
COPY alembic.ini ./
COPY alembic ./alembic

# 시작 스크립트 권한 부여
RUN chmod +x ./scripts/start.sh

CMD ["./scripts/start.sh"]

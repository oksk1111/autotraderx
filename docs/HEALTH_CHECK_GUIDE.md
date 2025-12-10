# Daily Health Check 설정 가이드

## 🎯 개요

매일 오전 9시에 자동으로 시스템 상태를 점검하고 Groq LLM이 분석한 리포트를 받습니다.

## 📋 구성 요소

### 1. 헬스 체크 스크립트
- **경로**: `backend/scripts/daily_health_check.py`
- **기능**:
  - 시스템 설정 확인
  - 거래 포지션 통계
  - Docker 컨테이너 상태
  - 에러 로그 분석
  - Groq LLM 리포트 생성

### 2. GitHub Actions 워크플로우
- **경로**: `.github/workflows/daily-health-check.yml`
- **스케줄**: 매일 오전 9시 (KST)
- **기능**: SSH로 서버 접속 → 헬스 체크 실행 → Slack 알림

## 🔧 설정 방법

### Step 1: Groq API 키 준비

`.env` 파일에 이미 있으니 확인만 하세요:
```bash
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
```

### Step 2: 로컬 테스트

```bash
# Docker 컨테이너에서 실행
cd /home/mingky/workspace/autotraderx
docker compose exec backend python /app/scripts/daily_health_check.py
```

예상 출력:
```
🏥 일일 헬스 체크 시작: 2025-12-07 09:00:00
📊 시스템 상태 수집 중...
🤖 Groq LLM 분석 중...
📤 알림 전송 중...
================================================================================
🏥 일일 헬스 체크 리포트
================================================================================
✅ **시스템 상태: 정상**

📊 **거래 활동 (최근 24시간)**
- 거래 신호: 96개 생성
- 실제 거래: 0건 (시장 횡보 구간)
- 보유 포지션: 0개

🔍 **분석**
현재 시장이 낮은 변동성(1-2%)을 보이고 있어 v4.0 시스템이 의도적으로 관망 중입니다.
...
================================================================================
✅ 일일 헬스 체크 완료
```

### Step 3: Slack 알림 설정 (선택)

1. Slack Webhook URL 생성:
   - https://api.slack.com/messaging/webhooks
   - "Create New Webhook" → 채널 선택 → URL 복사

2. `.env`에 추가:
```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX
```

3. 테스트:
```bash
docker compose exec backend python /app/scripts/daily_health_check.py
```

Slack에 메시지가 오면 성공!

### Step 4: GitHub Actions 설정 (자동화)

#### 4-1. GitHub Secrets 설정

Repository → Settings → Secrets and variables → Actions → New repository secret

추가할 Secrets:
```
SSH_PRIVATE_KEY: 서버 접속용 SSH 개인키 (id_rsa 내용)
SERVER_HOST: mingky-server.com (또는 IP)
SERVER_USER: mingky
GROQ_API_KEY: gsk_xxxxxxxxxxxxxxxxxxxx
SLACK_WEBHOOK_URL: https://hooks.slack.com/services/... (선택)
```

#### 4-2. SSH 키 설정

서버에 GitHub Actions가 접속할 수 있게 SSH 키 등록:

```bash
# 새 SSH 키 생성 (GitHub Actions 전용)
ssh-keygen -t rsa -b 4096 -C "github-actions@autotraderx" -f ~/.ssh/github_actions

# 공개키를 authorized_keys에 추가
cat ~/.ssh/github_actions.pub >> ~/.ssh/authorized_keys

# 개인키 내용 확인 (이걸 GitHub Secrets에 등록)
cat ~/.ssh/github_actions
```

#### 4-3. 워크플로우 활성화

파일이 이미 생성되었으니 Git에 푸시하면 자동 활성화:

```bash
git add .github/workflows/daily-health-check.yml
git add backend/scripts/daily_health_check.py
git add backend/requirements.txt
git commit -m "feat: Add daily health check system"
git push origin master
```

GitHub Repository → Actions 탭에서 "Daily Health Check" 워크플로우 확인!

#### 4-4. 수동 실행 테스트

GitHub Actions 탭 → "Daily Health Check" 선택 → "Run workflow" 버튼 클릭

## 📅 실행 스케줄

- **자동 실행**: 매일 오전 9시 (KST)
- **수동 실행**: GitHub Actions 탭에서 언제든 가능
- **로컬 실행**: `docker compose exec backend python /app/scripts/daily_health_check.py`

## 📊 리포트 내용

### 정상 상태 예시
```
✅ 시스템 상태: 정상

📊 거래 활동 (24시간)
- 신호 생성: 96개
- 실제 거래: 2건
- 수익률: +1.8%

🐳 Docker 컨테이너
- backend: running (healthy)
- worker: running (healthy)
- redis: running (healthy)
- postgres: running (healthy)

📝 권장사항
- 시스템 정상 작동 중입니다.
```

### 문제 발견 예시
```
⚠️ 시스템 상태: 주의

📊 거래 활동 (24시간)
- 신호 생성: 0개 ⚠️
- 에러: 47건 발견

🔴 발견된 문제
1. Worker 컨테이너 재시작 반복
2. ML 모델 로드 실패 (파일 없음)
3. Redis 연결 끊김

🛠️ 권장 조치사항
1. Worker 로그 확인: docker compose logs worker
2. ML 모델 재학습 필요
3. Redis 컨테이너 재시작
```

## 🔧 커스터마이징

### 알림 채널 추가

`daily_health_check.py`의 `send_notification()` 함수 수정:

```python
def send_notification(report: str):
    # 기존: 콘솔 + Slack
    
    # 이메일 추가
    import smtplib
    from email.message import EmailMessage
    
    msg = EmailMessage()
    msg['Subject'] = '🏥 AutoTraderX 일일 리포트'
    msg['From'] = 'noreply@autotraderx.com'
    msg['To'] = 'your-email@gmail.com'
    msg.set_content(report)
    
    with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
        smtp.starttls()
        smtp.login('your-email@gmail.com', 'app-password')
        smtp.send_message(msg)
```

### 실행 시간 변경

`.github/workflows/daily-health-check.yml`:

```yaml
on:
  schedule:
    # 오전 6시로 변경 (UTC 21:00)
    - cron: '0 21 * * *'
    
    # 하루 2번 (오전 9시, 오후 9시)
    - cron: '0 0,12 * * *'
```

### 분석 프롬프트 수정

`daily_health_check.py`의 `analyze_with_groq()` 함수에서 프롬프트 커스터마이징:

```python
prompt = f"""당신은 자동매매 시스템 모니터링 전문가입니다.

시스템 상태:
{json.dumps(health_data, indent=2, ensure_ascii=False)}

다음을 포함한 상세 리포트를 작성해주세요:
1. 시스템 상태 (정상/주의/경고)
2. 거래 성과 분석 (수익률, 승률)
3. 시장 상황 분석
4. 리스크 평가
5. 향후 전략 제안
"""
```

## 🚨 트러블슈팅

### "GROQ_API_KEY가 설정되지 않았습니다"
→ `.env` 파일 확인 후 컨테이너 재시작:
```bash
docker compose restart backend worker
```

### GitHub Actions SSH 연결 실패
→ SSH 키 권한 확인:
```bash
chmod 600 ~/.ssh/authorized_keys
chmod 700 ~/.ssh
```

### "docker.errors.DockerException"
→ Docker 소켓 권한 확인:
```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Groq API Rate Limit
→ 무료 플랜 제한(14,400 req/day)에 걸림. 1시간 후 재시도하거나 유료 플랜 고려.

## 📚 참고 자료

- [Groq API Documentation](https://console.groq.com/docs)
- [GitHub Actions Scheduling](https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows#schedule)
- [Slack Webhooks](https://api.slack.com/messaging/webhooks)

## 🎯 다음 단계

헬스 체크 시스템이 작동하면:

1. **주간 리포트 추가**: 월요일마다 지난주 통계 요약
2. **실시간 알림**: 에러 발생 시 즉시 Slack 알림
3. **대시보드 연동**: 프론트엔드에 헬스 상태 표시
4. **자동 복구**: 문제 감지 시 자동으로 컨테이너 재시작

---

**이제 매일 아침 9시에 자동으로 시스템 리포트를 받게 됩니다! 🎉**

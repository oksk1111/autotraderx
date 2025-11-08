# AutoTraderX 업데이트 가이드

## 📋 변경사항 요약

기획서에 따라 다음 기능들이 추가/개선되었습니다:

### ✨ 새로운 기능
1. **Ollama AI 통합** - DeepSeek-R1 모델 기반 자동 매매 판단
2. **뉴스 & 트렌드 수집** - NewsAPI 및 Google Trends 통합
3. **강화된 리스크 관리** - 트레일링 스톱, 슬리피지 방지
4. **AI 모니터 대시보드** - 실시간 AI 판단 로그 및 상태 확인

---

## 🚀 Ollama 설치 및 설정

### 1. Ollama 설치

#### Windows
```powershell
# Ollama 다운로드 및 설치
# https://ollama.com/download 에서 Windows 설치 파일 다운로드
# 설치 후 자동으로 서비스 시작됨
```

#### 설치 확인
```powershell
ollama --version
```

### 2. DeepSeek-R1 모델 다운로드

```powershell
# DeepSeek-R1 8B 모델 다운로드 (약 4.7GB)
ollama pull deepseek-r1:8b

# 다운로드 완료 확인
ollama list
```

### 3. Ollama 서비스 실행

```powershell
# Ollama는 설치 후 자동으로 백그라운드에서 실행됩니다
# 포트 11434에서 API 서버가 실행됨

# 상태 확인
curl http://localhost:11434/api/tags
```

---

## 🔧 프로젝트 설정

### 1. 환경 변수 설정

`.env` 파일이 이미 업데이트되었습니다. 추가 설정:

```env
# Ollama 설정 (Docker 환경)
OLLAMA_API_URL=http://host.docker.internal:11434
OLLAMA_MODEL=deepseek-r1:8b
USE_AI_DECISION=true

# 뉴스 API (선택사항)
# https://newsapi.org 에서 무료 API 키 발급
NEWS_API_KEY=your_api_key_here
```

### 2. Docker 컨테이너 재빌드 및 실행

```powershell
# 기존 컨테이너 중지
docker-compose down

# 새로운 의존성으로 이미지 재빌드
docker-compose build

# 컨테이너 실행
docker-compose up -d

# 로그 확인
docker-compose logs -f backend
```

---

## 📱 모바일 접속 설정 (외부 네트워크)

### 방법 1: ngrok 사용 (추천)

#### 1. ngrok 설치
```powershell
# Chocolatey로 설치
choco install ngrok

# 또는 https://ngrok.com/download 에서 다운로드
```

#### 2. ngrok 계정 생성 및 인증
```powershell
# https://dashboard.ngrok.com/signup 에서 무료 계정 생성
# 인증 토큰 설정
ngrok config add-authtoken YOUR_AUTH_TOKEN
```

#### 3. 터널 생성
```powershell
# 프론트엔드 (3000 포트)
ngrok http 3000

# 새 터미널에서 백엔드 (8000 포트)
ngrok http 8000
```

#### 4. URL 확인
ngrok이 제공하는 URL을 사용하여 모바일에서 접속:
- Frontend: `https://xxxx-xxx-xxx-xxx-xxx.ngrok-free.app`
- Backend: `https://yyyy-yyy-yyy-yyy-yyy.ngrok-free.app`

**프론트엔드 환경 변수 수정:**
```javascript
// frontend/src/services/api.js
const API_BASE_URL = 'https://yyyy-yyy-yyy-yyy-yyy.ngrok-free.app/api/v1';
```

---

### 방법 2: 로컬 네트워크 (같은 WiFi)

#### 1. PC의 로컬 IP 확인
```powershell
ipconfig
# IPv4 주소 확인 (예: 192.168.0.10)
```

#### 2. Docker Compose 수정
```yaml
# docker-compose.yml
services:
  backend:
    ports:
      - "0.0.0.0:8000:8000"  # 모든 네트워크에서 접근 가능
  
  frontend:
    ports:
      - "0.0.0.0:3000:3000"  # 모든 네트워크에서 접근 가능
```

#### 3. 방화벽 설정
```powershell
# Windows 방화벽에서 포트 8000, 3000 허용
# 제어판 > Windows Defender 방화벽 > 고급 설정 > 인바운드 규칙
```

#### 4. 모바일에서 접속
- Frontend: `http://192.168.0.10:3000`
- Backend: `http://192.168.0.10:8000`

**프론트엔드 환경 변수 수정:**
```javascript
// frontend/src/services/api.js
const API_BASE_URL = 'http://192.168.0.10:8000/api/v1';
```

---

### 방법 3: Cloudflare Tunnel (무료, 영구 URL)

#### 1. Cloudflare Tunnel 설치
```powershell
# Windows용 cloudflared 다운로드
# https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/
```

#### 2. 터널 생성
```powershell
cloudflared tunnel --url http://localhost:3000
```

---

## 🧪 테스트

### 1. Ollama 연결 테스트
```powershell
# API 직접 호출
curl -X POST http://localhost:11434/api/generate -d "{\"model\":\"deepseek-r1:8b\",\"prompt\":\"Hello\"}"
```

### 2. 백엔드 AI 엔드포인트 테스트
```powershell
# AI 상태 확인
curl http://localhost:8000/api/v1/ai/status

# AI 분석 실행
curl -X POST "http://localhost:8000/api/v1/ai/analyze?market=KRW-BTC"
```

### 3. 프론트엔드 접속
브라우저에서 `http://localhost:3000` 접속 후 AI 모니터 확인

---

## 📊 AI 트레이딩 사용법

### 1. 대시보드에서 AI 상태 확인
- 🟢 초록색: Ollama 정상 작동
- 🔴 빨간색: Ollama 중지 또는 연결 실패

### 2. AI 판단 실행
- "BTC 실시간 분석 실행" 버튼 클릭
- AI가 현재 시장을 분석하여 매수/매도/유지 결정

### 3. AI 로그 확인
- 실시간으로 AI의 판단 이유와 신뢰도 확인
- 매수(📈), 매도(📉), 유지(⏸️) 신호 표시

### 4. AI ON/OFF 토글
- AI 판단을 끄면 기존 기술적 분석만 사용
- 필요에 따라 전환 가능

---

## 🔍 문제 해결

### Ollama 연결 실패
```powershell
# Ollama 서비스 재시작
# 작업 관리자 > 서비스 > Ollama 재시작

# 또는 명령어로
net stop ollama
net start ollama
```

### Docker에서 host.docker.internal 접근 안됨
Docker Desktop 설정에서 "Use WSL 2 based engine" 활성화

### 포트 충돌
```powershell
# 포트 사용 중인 프로세스 확인
netstat -ano | findstr :11434
netstat -ano | findstr :3000
netstat -ano | findstr :8000
```

---

## 📈 성능 최적화

### 모델 선택
- **deepseek-r1:8b** (추천) - 빠르고 정확, 4.7GB
- **qwen2:14b** - 더 정밀, 느림, 8GB
- **llama3:8b** - 빠름, 기본 성능, 4.3GB

### GPU 가속 (선택)
Ollama는 NVIDIA GPU를 자동 감지하여 사용합니다.

---

## 📞 지원

문제 발생 시:
1. Docker 로그 확인: `docker-compose logs -f`
2. Ollama 로그 확인: `%LOCALAPPDATA%\Ollama\ollama.log`
3. 백엔드 API 문서: `http://localhost:8000/docs`

---

**업데이트 완료! 🎉**

이제 AI 기반 자동 매매 시스템이 준비되었습니다.

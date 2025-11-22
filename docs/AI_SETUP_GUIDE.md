# AI 엔진 설정 가이드

AutoTraderX는 두 가지 AI 엔진을 지원합니다:
1. **Ollama** (로컬 실행)
2. **Groq** (클라우드 API)

## 🔧 설정 방법

### 1. Ollama 사용 (로컬)

**장점:**
- 완전 무료
- 데이터 프라이버시 보장
- 인터넷 연결 불필요

**단점:**
- GPU/CPU 리소스 필요
- 상대적으로 느린 응답 속도

**설정:**
```bash
# .env 파일에서
AI_PROVIDER=ollama
OLLAMA_API_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen2.5:7b
```

**모델 다운로드:**
```bash
# 터미널에서 실행
ollama pull qwen2.5:7b

# 또는 다른 모델
ollama pull llama3.1:8b
ollama pull gemma2:9b
```

**추천 모델:**
- `qwen2.5:7b` - 속도와 성능의 균형 (추천) ⭐
- `llama3.1:8b` - 빠른 속도
- `gemma2:9b` - 안정적인 성능

---

### 2. Groq 사용 (클라우드 API)

**장점:**
- 초고속 응답 속도 (Ollama보다 5-10배 빠름) ⚡
- 로컬 리소스 불필요
- 강력한 모델 (Llama 3.1 70B 등)

**단점:**
- API 키 필요 (무료 티어 제공)
- 인터넷 연결 필수
- 일일 요청 제한 (무료: 14,400 requests/day)

**설정 단계:**

#### 1) API 키 발급
1. [Groq Console](https://console.groq.com/keys) 접속
2. 회원가입 (GitHub 계정으로 간편 가입)
3. "Create API Key" 클릭
4. API 키 복사

#### 2) 환경 변수 설정
```bash
# .env 파일에서
AI_PROVIDER=groq
GROQ_API_KEY=gsk_your_api_key_here
GROQ_MODEL=llama-3.1-70b-versatile
```

#### 3) 패키지 설치
```bash
cd backend
pip install groq==0.11.0
```

**사용 가능한 모델:**
- `llama-3.1-70b-versatile` - 가장 강력 (추천) ⭐⭐⭐
- `llama-3.1-8b-instant` - 가장 빠름 ⚡
- `mixtral-8x7b-32768` - 긴 컨텍스트
- `gemma2-9b-it` - 효율적

---

## 🔄 AI 엔진 전환 방법

### 방법 1: .env 파일 수정
```bash
# Ollama로 전환
AI_PROVIDER=ollama

# Groq로 전환
AI_PROVIDER=groq
```

### 방법 2: 환경 변수로 직접 설정
```bash
# Docker Compose 재시작
docker-compose down
AI_PROVIDER=groq docker-compose up -d
```

---

## 📊 성능 비교

| 항목 | Ollama (Qwen 7B) | Groq (Llama 70B) |
|------|------------------|------------------|
| 응답 속도 | 5-15초 | 0.5-2초 ⚡ |
| 모델 크기 | 4.7GB | - |
| 비용 | 무료 | 무료 (제한 있음) |
| 품질 | 좋음 | 매우 좋음 ⭐ |
| 리소스 사용 | 높음 (로컬 GPU/CPU) | 없음 |

---

## 🛠️ 문제 해결

### Ollama 연결 오류
```bash
# Ollama 서비스 상태 확인
ollama list

# Ollama 재시작
ollama serve
```

### Groq API 키 오류
- API 키가 `gsk_`로 시작하는지 확인
- [Groq Console](https://console.groq.com/keys)에서 키 상태 확인
- 무료 한도 초과 여부 확인

### 모델 다운로드 실패 (Ollama)
```bash
# 저장 공간 확인
df -h

# 기존 모델 삭제
ollama rm deepseek-r1:8b
ollama rm old-model-name

# 다시 다운로드
ollama pull qwen2.5:7b
```

---

## 💡 추천 사용 시나리오

### 개발/테스트 환경
→ **Ollama** (로컬에서 자유롭게 테스트)

### 프로덕션 환경 (빠른 응답 필요)
→ **Groq** (초고속 응답)

### 데이터 보안 중요
→ **Ollama** (로컬에서만 실행)

### 제한된 로컬 리소스
→ **Groq** (클라우드 실행)

---

## 📝 API 엔드포인트

### AI 상태 확인
```bash
GET /api/ai/status
```

### 모델 목록 조회
```bash
GET /api/ai/models
```

### 시장 분석 (AI 사용)
```bash
POST /api/ai/analyze?market=KRW-BTC&use_ai=true
```

---

## 🚀 빠른 시작 (Groq 추천)

```bash
# 1. API 키 발급
# https://console.groq.com/keys

# 2. .env 파일 수정
AI_PROVIDER=groq
GROQ_API_KEY=gsk_your_api_key_here

# 3. 패키지 설치
cd backend
pip install groq

# 4. 서비스 재시작
docker-compose restart backend

# 5. 테스트
curl http://localhost:8000/api/ai/status
```

완료! 이제 초고속 AI 트레이딩을 경험하세요 🚀

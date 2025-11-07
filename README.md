# AutoTraderX

업비트 오픈 API 기반 실시간 코인 단기 자동 매매 시스템

## 📋 프로젝트 개요

AutoTraderX는 업비트 API를 활용한 AI 기반 실시간 암호화폐 자동 매매 시스템입니다. 
단기 스캘핑 전략을 사용하며, 리스크를 최소화한 알고리즘 트레이딩을 제공합니다.

## 🚀 주요 기능

- ✅ 실시간 시세 데이터 수집 및 분석
- ✅ AI 기반 매매 패턴 인식
- ✅ 자동 매수/매도 실행
- ✅ 손절/익절 자동 설정
- ✅ 웹 기반 실시간 모니터링 대시보드
- ✅ 백테스트 및 전략 시뮬레이션
- ✅ 리스크 관리 시스템

## 🛠 기술 스택

### Backend
- Python 3.11+
- FastAPI
- PostgreSQL
- Redis
- Celery

### Frontend
- React.js
- TailwindCSS
- WebSocket

### AI/ML
- PyTorch
- scikit-learn
- pandas, numpy

### Infrastructure
- Docker
- Nginx

## 📁 프로젝트 구조

```
autotraderx/
├── backend/
│   ├── app/
│   │   ├── api/              # API 엔드포인트
│   │   ├── core/             # 코어 설정 및 보안
│   │   ├── models/           # 데이터베이스 모델
│   │   ├── services/         # 비즈니스 로직
│   │   │   ├── upbit/        # 업비트 API 통합
│   │   │   ├── trading/      # 매매 엔진
│   │   │   ├── indicators/   # 기술적 지표
│   │   │   └── ai/           # AI 모델
│   │   └── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── services/
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

## 🔧 설치 및 실행

### 사전 요구사항
- Docker & Docker Compose
- 업비트 API 키 (액세스 키, 시크릿 키)

### 환경 변수 설정

`.env` 파일을 생성하고 다음 정보를 입력하세요:

```env
# Upbit API
UPBIT_ACCESS_KEY=your_access_key
UPBIT_SECRET_KEY=your_secret_key

# Database
POSTGRES_USER=autotraderx
POSTGRES_PASSWORD=your_password
POSTGRES_DB=autotraderx_db

# Redis
REDIS_HOST=redis
REDIS_PORT=6379

# Security
SECRET_KEY=your_secret_key
ENCRYPTION_KEY=your_encryption_key
```

### Docker로 실행

```bash
# 전체 서비스 시작
docker-compose up -d

# 백엔드만 실행
docker-compose up -d backend

# 로그 확인
docker-compose logs -f
```

### 로컬 개발 환경

```bash
# 백엔드
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# 프론트엔드
cd frontend
npm install
npm start
```

## 📊 매매 전략

### 기술적 지표
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- MFI (Money Flow Index)
- 이동평균선 (MA)

### 매수 조건
- 상승 추세 전환 지표 2개 이상 일치
- 거래량 증가 + 단기 이동평균선 상향 돌파
- RSI 상승세

### 매도 조건
- 거래량 감소 + 수익률 목표 도달
- MACD 데드크로스
- 손절 라인 도달 (-1% ~ -2%)

## 🔒 보안

- API 키 AES256 암호화 저장
- 거래 한도 제어
- 슬리피지 처리
- 모든 거래 로그 기록

## ⚠️ 주의사항

- 이 시스템은 교육 및 연구 목적으로 개발되었습니다.
- 실제 거래 시 발생하는 모든 손실에 대한 책임은 사용자에게 있습니다.
- 충분한 백테스트와 소액 테스트를 거친 후 사용하시기 바랍니다.

## 📝 라이선스

MIT License

## 🔗 참고 자료

- [업비트 Open API 문서](https://docs.upbit.com/)
- [FastAPI 공식 문서](https://fastapi.tiangolo.com/)
- [React 공식 문서](https://react.dev/)

## 👥 기여

이슈와 PR은 언제나 환영합니다!

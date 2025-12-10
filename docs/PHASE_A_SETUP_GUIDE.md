# Phase A 인증 시스템 설정 가이드

## 📋 개요

Phase A는 다음 기능을 구현합니다:
- ✅ OAuth 로그인 (Google, Naver, Kakao)
- ✅ JWT 인증 (Access Token + Refresh Token)
- ✅ Upbit API 키 암호화 저장
- ✅ 약관 동의 플로우
- ✅ 감사 로그 (Audit Log)

---

## 🚀 설정 단계

### 1. 패키지 설치

```bash
cd backend
pip install -r requirements.txt
```

새로 추가된 패키지:
- `cryptography==42.0.5` - Fernet 암호화
- `authlib==1.3.0` - OAuth 클라이언트
- `itsdangerous==2.1.2` - 보안 유틸리티

---

### 2. 환경변수 설정

#### 2.1. 암호화 키 생성

```bash
# Fernet 암호화 키 생성
docker compose exec backend python -c "from app.core.encryption import generate_encryption_key; print(generate_encryption_key())"

# JWT 비밀키 생성
docker compose exec backend python -c "from app.core.jwt import generate_jwt_secret; print(generate_jwt_secret())"
```

#### 2.2. `.env` 파일 수정

생성된 키를 `.env` 파일에 추가:

```bash
# 암호화 키 (위에서 생성한 값으로 변경)
ENCRYPTION_KEY=your_generated_fernet_key_here

# JWT 비밀키 (위에서 생성한 값으로 변경)
JWT_SECRET_KEY=your_generated_jwt_secret_here
```

---

### 3. OAuth 앱 등록

#### 3.1. Google OAuth

1. [Google Cloud Console](https://console.cloud.google.com/apis/credentials) 접속
2. 프로젝트 생성 또는 선택
3. **OAuth 2.0 클라이언트 ID** 생성
   - 애플리케이션 유형: **웹 애플리케이션**
   - 승인된 리디렉션 URI:
     - `http://localhost:3000/auth/google/callback` (개발)
     - `https://yourdomain.com/auth/google/callback` (배포)
4. 생성된 클라이언트 ID와 Secret을 `.env`에 추가:

```bash
GOOGLE_CLIENT_ID=123456789-abcdefgh.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxxxx
GOOGLE_REDIRECT_URI=http://localhost:3000/auth/google/callback
```

#### 3.2. Naver OAuth

1. [네이버 개발자센터](https://developers.naver.com/apps/#/register) 접속
2. 애플리케이션 등록
   - 사용 API: **네이버 로그인**
   - 서비스 URL: `http://localhost:3000` (개발)
   - Callback URL: `http://localhost:3000/auth/naver/callback`
3. 생성된 Client ID와 Secret을 `.env`에 추가:

```bash
NAVER_CLIENT_ID=your_naver_client_id
NAVER_CLIENT_SECRET=your_naver_client_secret
NAVER_REDIRECT_URI=http://localhost:3000/auth/naver/callback
```

#### 3.3. Kakao OAuth

1. [카카오 개발자센터](https://developers.kakao.com/console/app) 접속
2. 애플리케이션 추가
3. **플랫폼 설정 > Web** 추가
   - 사이트 도메인: `http://localhost:3000`
4. **카카오 로그인** 활성화
   - Redirect URI: `http://localhost:3000/auth/kakao/callback`
5. REST API 키를 `.env`에 추가:

```bash
KAKAO_CLIENT_ID=your_rest_api_key
KAKAO_REDIRECT_URI=http://localhost:3000/auth/kakao/callback
```

---

### 4. 데이터베이스 마이그레이션

```bash
# 컨테이너 빌드 및 실행
docker compose build backend
docker compose up -d

# 마이그레이션 실행
docker compose exec backend alembic upgrade head
```

생성되는 테이블:
- `users` - 사용자 계정 (OAuth)
- `api_keys` - Upbit API 키 (암호화)
- `audit_logs` - 감사 로그

---

### 5. API 테스트

#### 5.1. 서버 실행 확인

```bash
curl http://localhost:8000/api/health
```

#### 5.2. OAuth URL 생성 테스트

```bash
# Google OAuth URL
curl http://localhost:8000/api/auth/oauth/google/url

# Naver OAuth URL
curl http://localhost:8000/api/auth/oauth/naver/url

# Kakao OAuth URL
curl http://localhost:8000/api/auth/oauth/kakao/url
```

응답 예시:
```json
{
  "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?...",
  "state": "random_state_string"
}
```

#### 5.3. 사용자 프로필 조회 (인증 필요)

```bash
# 1. OAuth 로그인 후 access_token 획득
# 2. 헤더에 토큰 포함하여 요청
curl -H "Authorization: Bearer your_access_token" \
     http://localhost:8000/api/auth/me
```

---

## 📚 API 엔드포인트

### 인증

| Method | Endpoint | 설명 |
|--------|----------|------|
| GET | `/api/auth/oauth/{provider}/url` | OAuth 인증 URL 생성 |
| POST | `/api/auth/oauth/{provider}/callback` | OAuth 콜백 처리 및 JWT 발급 |
| POST | `/api/auth/refresh` | Refresh Token으로 Access Token 갱신 |
| GET | `/api/auth/me` | 현재 사용자 프로필 조회 |

### 약관

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/auth/terms/agree` | 이용약관 동의 |

### API 키 관리

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/auth/api-keys` | Upbit API 키 등록 (자동 검증) |
| GET | `/api/auth/api-keys` | 등록된 API 키 목록 |
| DELETE | `/api/auth/api-keys/{key_id}` | API 키 삭제 |

---

## 🔒 보안 고려사항

### 1. 암호화 키 관리

- **ENCRYPTION_KEY**: Upbit API 키를 암호화하는 Fernet 키
  - 절대 Git에 커밋하지 마세요
  - 배포 환경별로 다른 키 사용
  - 키 로테이션 정책 수립 (연 1회 권장)

### 2. JWT 토큰

- **Access Token**: 15분 수명, API 인증용
- **Refresh Token**: 7일 수명, Access Token 갱신용
- HTTPS 사용 필수 (배포 환경)

### 3. API 키 권한

- Upbit API 키는 **조회 + 거래** 권한만 허용
- **출금 권한은 절대 허용하지 마세요**

### 4. CORS 설정

`backend/app/main.py`에서 배포 시 `allow_origins` 수정:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # 특정 도메인만 허용
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    allow_credentials=True,
)
```

---

## 🐛 문제 해결

### 1. 마이그레이션 실패

```bash
# 마이그레이션 상태 확인
docker compose exec backend alembic current

# 마이그레이션 히스토리 확인
docker compose exec backend alembic history

# 롤백
docker compose exec backend alembic downgrade -1
```

### 2. OAuth 설정 누락

에러:
```
ValueError: Google OAuth 설정이 필요합니다.
```

해결:
- `.env` 파일에 해당 OAuth 환경변수가 있는지 확인
- 컨테이너 재시작: `docker compose restart backend`

### 3. 암호화 키 오류

에러:
```
ValueError: ENCRYPTION_KEY 환경변수가 설정되지 않았습니다.
```

해결:
```bash
# 키 생성
docker compose exec backend python -c "from app.core.encryption import generate_encryption_key; print(generate_encryption_key())"

# .env에 추가 후 재시작
docker compose restart backend
```

---

## 📖 다음 단계

Phase A 완료 후:

1. **프론트엔드 UI 구현** (Task #8)
   - OAuth 로그인 버튼
   - API 키 등록 폼
   - 약관 동의 체크박스

2. **Phase B 진행** (과금/정산)
   - 요금제 설계
   - 결제 연동
   - 영수증 발행

3. **Phase C** (GPU 자동학습)
   - 클라우드 스팟 인스턴스
   - 모델 아티팩트 배포

---

## 📞 지원

문제가 발생하면:
1. 로그 확인: `docker compose logs backend --tail=100`
2. DB 상태 확인: `docker compose exec postgres psql -U autotrader -d autotrader -c "\dt"`
3. 환경변수 확인: `docker compose exec backend env | grep -E "ENCRYPTION|JWT|OAUTH"`

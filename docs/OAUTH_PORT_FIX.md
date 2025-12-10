# Google OAuth 포트 문제 해결 완료

## 🐛 문제

사용자가 Google 로그인 시도 시 다음 에러 발생:
```
http://localhost:3000/auth/google/callback?state=...&code=...
```

프론트엔드는 **4173 포트**에서 실행 중이지만, OAuth가 **3000 포트**로 리디렉션되어 "페이지를 찾을 수 없음" 에러

---

## 🔍 원인

1. `.env` 파일에 `GOOGLE_REDIRECT_URI` 중복:
   ```env
   GOOGLE_REDIRECT_URI=http://localhost:4173/auth/google/callback  # 올바른 값
   GOOGLE_REDIRECT_URI=http://localhost:3000/auth/google/callback  # 중복된 값 (덮어씀)
   ```

2. `oauth.py`와 `config.py`의 기본값이 3000 포트로 하드코딩:
   ```python
   GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:3000/...")
   ```

---

## ✅ 해결 방법

### 1. `.env` 파일 수정
**위치**: `/home/mingky/workspace/autotraderx/.env`

**수정 전**:
```env
GOOGLE_REDIRECT_URI=http://localhost:4173/auth/google/callback
GOOGLE_REDIRECT_URI=http://localhost:3000/auth/google/callback  # ❌ 중복
```

**수정 후**:
```env
GOOGLE_REDIRECT_URI=http://localhost:4173/auth/google/callback  # ✅ 단일 값
```

### 2. `oauth.py` 기본값 수정
**위치**: `/backend/app/core/oauth.py`

```python
# 수정 전
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:3000/auth/google/callback")

# 수정 후
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:4173/auth/google/callback")
```

### 3. `config.py` 기본값 수정
**위치**: `/backend/app/core/config.py`

```python
# 수정 전
google_redirect_uri: str = "http://localhost:3000/auth/google/callback"

# 수정 후
google_redirect_uri: str = "http://localhost:4173/auth/google/callback"
```

### 4. 백엔드 재시작
```bash
docker compose up -d --force-recreate backend
```

---

## 🎯 Google Cloud Console 설정 (필수!)

### ⚠️ 중요: 다음 URI를 Google Cloud Console에 추가해야 합니다

1. **Google Cloud Console** 접속:
   https://console.cloud.google.com/apis/credentials

2. OAuth 2.0 클라이언트 ID 선택:
   `491568907388-jmb36mpph4eali6lkg8flatj7vl0si5a`

3. **승인된 JavaScript 원본** 섹션에 추가:
   ```
   http://localhost:4173
   ```

4. **승인된 리디렉션 URI** 섹션에 추가:
   ```
   http://localhost:4173/auth/google/callback
   ```

5. **저장** 버튼 클릭

---

## 🧪 테스트

### 1. 백엔드 OAuth URL 확인
```bash
curl -s "http://localhost:8000/api/auth/oauth/google/url" | jq .
```

**예상 출력**:
```json
{
  "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth?...redirect_uri=http%3A%2F%2Flocalhost%3A4173%2Fauth%2Fgoogle%2Fcallback...",
  "state": "..."
}
```

### 2. 프론트엔드에서 로그인 테스트
1. http://localhost:4173 접속
2. "Google로 로그인" 클릭
3. Google 계정 선택
4. **자동으로 http://localhost:4173/auth/google/callback 으로 리디렉션** ✅
5. JWT 토큰 저장 후 대시보드 이동

---

## 📊 변경 사항 요약

| 파일 | 변경 내용 |
|------|-----------|
| `.env` | `GOOGLE_REDIRECT_URI` 중복 제거, 4173 포트로 통일 |
| `backend/app/core/oauth.py` | 기본값 3000 → 4173 포트로 변경 |
| `backend/app/core/config.py` | 기본값 3000 → 4173 포트로 변경 |

---

## ✅ 확인 결과

```bash
$ curl -s "http://localhost:8000/api/auth/oauth/google/url" | python3 -c "..."
✅ Redirect URI: http://localhost:4173/auth/google/callback
```

---

## 🚀 다음 단계

1. ✅ `.env` 파일 수정 완료
2. ✅ 백엔드 코드 수정 완료
3. ✅ 백엔드 재시작 완료
4. ⏳ **Google Cloud Console에서 URI 추가 필요** (사용자 작업)
5. ⏳ 로그인 테스트

**작업 완료 후 다시 테스트해주세요!**

---

**작성일**: 2025년 12월 8일  
**이슈**: Google OAuth 포트 불일치 (3000 vs 4173)  
**상태**: ✅ 해결 (Google Console 설정 대기)

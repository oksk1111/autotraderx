"""
인증 관련 API 라우터
- OAuth 로그인 (Google, Naver, Kakao)
- JWT 토큰 발급/갱신
- 약관 동의
- API 키 등록/검증
"""
from fastapi import APIRouter, Depends, HTTPException, status, Header
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import secrets

from app.db.session import get_db
from app.models.user import User, ApiKey, AuditLog, OAuthProvider, AuditLogAction
from app.schemas.auth import (
    OAuthLoginRequest, TokenResponse, UserProfileResponse,
    TermsAgreementRequest, ApiKeyRegisterRequest, ApiKeyResponse,
    ApiKeyValidationResponse
)
from app.core.oauth import get_oauth_client
from app.core.jwt import get_jwt_manager
from app.core.encryption import get_encryption_manager
import pyupbit

router = APIRouter(tags=["Authentication"])  # prefix는 api/__init__.py에서 설정


# ==================== OAuth 로그인 ====================

@router.get("/oauth/{provider}/url")
async def get_oauth_url(provider: str):
    """
    OAuth 인증 URL 생성
    
    프론트엔드에서 이 URL로 리디렉션하면 OAuth 제공자 로그인 페이지로 이동
    """
    try:
        client = get_oauth_client(provider)
        state = secrets.token_urlsafe(16)
        
        # 실제 환경에서는 state를 Redis에 저장하고 검증해야 함 (CSRF 방어)
        url = client.get_authorization_url(state=state)
        
        return {
            "authorization_url": url,
            "state": state
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/oauth/{provider}/callback", response_model=TokenResponse)
async def oauth_callback(
    provider: str,
    request: OAuthLoginRequest,
    db: Session = Depends(get_db)
):
    """
    OAuth 콜백 처리
    
    1. 인증 코드로 액세스 토큰 획득
    2. 사용자 정보 조회
    3. DB에 사용자 생성 또는 업데이트
    4. JWT 토큰 발급
    """
    try:
        # OAuth 클라이언트로 사용자 정보 가져오기
        client = get_oauth_client(provider)
        
        # 액세스 토큰 획득
        if provider == "naver":
            token_data = await client.get_access_token(request.code, request.state)
        else:
            token_data = await client.get_access_token(request.code)
        
        oauth_access_token = token_data["access_token"]
        
        # 사용자 정보 조회
        user_info = await client.get_user_info(oauth_access_token)
        
        # DB에서 사용자 조회 또는 생성
        oauth_id = f"{provider}:{user_info['oauth_id']}"
        user = db.query(User).filter(User.oauth_id == oauth_id).first()
        
        if not user:
            # 신규 사용자 생성
            user = User(
                oauth_provider=OAuthProvider(provider),
                oauth_id=oauth_id,
                email=user_info["email"],
                name=user_info.get("name"),
                profile_image=user_info.get("profile_image"),
                last_login_at=datetime.utcnow()
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            
            # 감사 로그 - 회원가입
            audit_log = AuditLog(
                user_id=user.id,
                action=AuditLogAction.REGISTER,
                details=f"OAuth 회원가입: {provider}",
                success=True
            )
            db.add(audit_log)
            db.commit()
        else:
            # 기존 사용자 로그인 시간 업데이트
            user.last_login_at = datetime.utcnow()
            db.commit()
            
            # 감사 로그 - 로그인
            audit_log = AuditLog(
                user_id=user.id,
                action=AuditLogAction.LOGIN,
                details=f"OAuth 로그인: {provider}",
                success=True
            )
            db.add(audit_log)
            db.commit()
        
        # JWT 토큰 발급
        jwt_manager = get_jwt_manager()
        token_payload = {
            "user_id": user.id,
            "email": user.email,
            "role": user.role.value
        }
        
        access_token = jwt_manager.create_access_token(token_payload)
        refresh_token = jwt_manager.create_refresh_token(token_payload)
        
        # 사용자 프로필 정보 (SQLAlchemy 모델을 Pydantic으로 자동 변환)
        user_profile = UserProfileResponse.model_validate(user)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=900,  # 15분
            user=user_profile
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth 인증 실패: {str(e)}"
        )


# ==================== 토큰 갱신 ====================

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str,
    db: Session = Depends(get_db)
):
    """
    Refresh Token으로 새로운 Access Token 발급
    """
    jwt_manager = get_jwt_manager()
    payload = jwt_manager.verify_token(refresh_token, expected_type="refresh")
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 Refresh Token"
        )
    
    # 사용자 확인
    user = db.query(User).filter(User.id == payload["user_id"]).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자를 찾을 수 없거나 비활성화됨"
        )
    
    # 새로운 토큰 발급
    token_payload = {
        "user_id": user.id,
        "email": user.email,
        "role": user.role.value
    }
    
    new_access_token = jwt_manager.create_access_token(token_payload)
    new_refresh_token = jwt_manager.create_refresh_token(token_payload)
    
    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=900
    )


# ==================== 현재 사용자 정보 ====================

async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> User:
    """
    JWT 토큰으로 현재 사용자 인증
    
    헤더 형식: Authorization: Bearer <token>
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증 토큰이 필요합니다"
        )
    
    token = authorization.replace("Bearer ", "")
    jwt_manager = get_jwt_manager()
    token_data = jwt_manager.decode_token(token)
    
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰"
        )
    
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="사용자를 찾을 수 없거나 비활성화됨"
        )
    
    return user


@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """현재 로그인한 사용자 프로필 조회"""
    return UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        profile_image=current_user.profile_image,
        oauth_provider=current_user.oauth_provider.value,
        role=current_user.role.value,
        is_active=current_user.is_active,
        terms_agreed=current_user.terms_agreed,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at
    )


# ==================== 약관 동의 ====================

@router.post("/terms/agree")
async def agree_to_terms(
    request: TermsAgreementRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    이용약관 및 개인정보처리방침 동의
    
    필수: terms_agreed, privacy_agreed
    선택: marketing_agreed
    """
    current_user.terms_agreed = request.terms_agreed
    current_user.privacy_agreed = request.privacy_agreed
    current_user.marketing_agreed = request.marketing_agreed
    current_user.terms_agreed_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "message": "약관 동의가 완료되었습니다",
        "terms_agreed": current_user.terms_agreed,
        "privacy_agreed": current_user.privacy_agreed,
        "marketing_agreed": current_user.marketing_agreed
    }


# ==================== API 키 관리 ====================

@router.post("/api-keys", response_model=ApiKeyResponse)
async def register_api_key(
    request: ApiKeyRegisterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upbit API 키 등록
    
    1. 키 유효성 검증 (잔고 조회 테스트)
    2. 암호화 저장
    """
    # 1. 키 유효성 검증
    try:
        upbit = pyupbit.Upbit(request.access_key, request.secret_key)
        balance = upbit.get_balance("KRW")
        
        if balance is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="API 키가 유효하지 않습니다. 잔고 조회에 실패했습니다."
            )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"API 키 검증 실패: {str(e)}"
        )
    
    # 2. 암호화 저장
    encryption_manager = get_encryption_manager()
    encrypted_access, encrypted_secret = encryption_manager.encrypt_api_keys(
        request.access_key,
        request.secret_key
    )
    
    api_key = ApiKey(
        user_id=current_user.id,
        encrypted_access_key=encrypted_access,
        encrypted_secret_key=encrypted_secret,
        key_name=request.key_name,
        last_validated_at=datetime.utcnow()
    )
    
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    
    # 감사 로그
    audit_log = AuditLog(
        user_id=current_user.id,
        action=AuditLogAction.API_KEY_ADD,
        resource="api_key",
        resource_id=str(api_key.id),
        success=True
    )
    db.add(audit_log)
    db.commit()
    
    return ApiKeyResponse(
        id=api_key.id,
        key_name=api_key.key_name,
        is_active=api_key.is_active,
        last_validated_at=api_key.last_validated_at,
        created_at=api_key.created_at,
        access_key_preview=request.access_key[:4] + "****"
    )


@router.get("/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """등록된 API 키 목록 조회"""
    api_keys = db.query(ApiKey).filter(ApiKey.user_id == current_user.id).all()
    
    # 복호화하여 앞 4자리만 표시
    encryption_manager = get_encryption_manager()
    results = []
    
    for key in api_keys:
        decrypted_access, _ = encryption_manager.decrypt_api_keys(
            key.encrypted_access_key,
            key.encrypted_secret_key
        )
        
        results.append(ApiKeyResponse(
            id=key.id,
            key_name=key.key_name,
            is_active=key.is_active,
            last_validated_at=key.last_validated_at,
            created_at=key.created_at,
            access_key_preview=decrypted_access[:4] + "****"
        ))
    
    return results


@router.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """API 키 삭제"""
    api_key = db.query(ApiKey).filter(
        ApiKey.id == key_id,
        ApiKey.user_id == current_user.id
    ).first()
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API 키를 찾을 수 없습니다"
        )
    
    db.delete(api_key)
    db.commit()
    
    # 감사 로그
    audit_log = AuditLog(
        user_id=current_user.id,
        action=AuditLogAction.API_KEY_DELETE,
        resource="api_key",
        resource_id=str(key_id),
        success=True
    )
    db.add(audit_log)
    db.commit()
    
    return {"message": "API 키가 삭제되었습니다"}

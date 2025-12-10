"""
OAuth 인증 관련 Pydantic 스키마
"""
from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, Literal
from datetime import datetime


class OAuthLoginRequest(BaseModel):
    """OAuth 로그인 요청"""
    code: str = Field(..., description="OAuth 인증 코드")
    state: Optional[str] = Field(None, description="CSRF 방지용 state 값")


class TokenResponse(BaseModel):
    """토큰 응답"""
    access_token: str = Field(..., description="Access Token (15분)")
    refresh_token: str = Field(..., description="Refresh Token (7일)")
    token_type: str = Field(default="bearer", description="토큰 타입")
    expires_in: int = Field(default=900, description="만료 시간 (초)")
    user: "UserProfileResponse" = Field(..., description="사용자 정보")


class UserProfileResponse(BaseModel):
    """사용자 프로필 응답"""
    id: int
    email: EmailStr
    name: Optional[str] = None
    profile_image: Optional[str] = None
    oauth_provider: str
    role: str
    is_active: bool
    terms_agreed: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None
    
    @field_validator('oauth_provider', 'role', mode='before')
    @classmethod
    def extract_enum_value(cls, v):
        """Enum 타입을 문자열로 변환"""
        if hasattr(v, 'value'):
            return v.value
        return v
    
    class Config:
        from_attributes = True  # SQLAlchemy 모델에서 자동 변환


class TermsAgreementRequest(BaseModel):
    """약관 동의 요청"""
    terms_agreed: bool = Field(..., description="이용약관 동의")
    privacy_agreed: bool = Field(..., description="개인정보처리방침 동의")
    marketing_agreed: bool = Field(default=False, description="마케팅 수신 동의 (선택)")


class ApiKeyRegisterRequest(BaseModel):
    """API 키 등록 요청"""
    access_key: str = Field(..., min_length=10, description="Upbit Access Key")
    secret_key: str = Field(..., min_length=10, description="Upbit Secret Key")
    key_name: Optional[str] = Field(None, max_length=100, description="키 별칭")


class ApiKeyResponse(BaseModel):
    """API 키 응답 (민감 정보 제외)"""
    id: int
    key_name: Optional[str] = None
    is_active: bool
    last_validated_at: Optional[datetime] = None
    created_at: datetime
    
    # 보안상 실제 키는 반환하지 않음
    access_key_preview: str = Field(..., description="Access Key 앞 4자리만 표시")


class ApiKeyValidationResponse(BaseModel):
    """API 키 검증 결과"""
    valid: bool = Field(..., description="키 유효성")
    balance: Optional[float] = Field(None, description="KRW 잔고 (검증 성공 시)")
    error: Optional[str] = Field(None, description="에러 메시지 (실패 시)")

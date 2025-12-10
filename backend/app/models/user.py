"""
사용자 및 인증 관련 모델
- User: 사용자 계정 (OAuth 로그인)
- ApiKey: Upbit API 키 (암호화 저장)
- AuditLog: 감사 로그
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base
import enum


class OAuthProvider(str, enum.Enum):
    """OAuth 제공자"""
    GOOGLE = "google"
    NAVER = "naver"
    KAKAO = "kakao"


class UserRole(str, enum.Enum):
    """사용자 권한"""
    USER = "user"          # 일반 사용자
    ADMIN = "admin"        # 관리자
    DEVELOPER = "developer"  # 개발자


class User(Base):
    """사용자 테이블"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    
    # OAuth 정보
    oauth_provider = Column(SQLEnum(OAuthProvider), nullable=False, comment="OAuth 제공자")
    oauth_id = Column(String(255), nullable=False, unique=True, index=True, comment="OAuth 사용자 ID")
    
    # 프로필 정보
    email = Column(String(255), nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=True)
    profile_image = Column(String(500), nullable=True)
    
    # 권한
    role = Column(SQLEnum(UserRole), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, comment="계정 활성화 여부")
    
    # 약관 동의
    terms_agreed = Column(Boolean, default=False, nullable=False, comment="이용약관 동의")
    privacy_agreed = Column(Boolean, default=False, nullable=False, comment="개인정보처리방침 동의")
    marketing_agreed = Column(Boolean, default=False, nullable=False, comment="마케팅 수신 동의")
    terms_agreed_at = Column(DateTime(timezone=True), nullable=True, comment="약관 동의 일시")
    
    # 타임스탬프
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    
    # 관계
    api_keys = relationship("ApiKey", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")


class ApiKey(Base):
    """Upbit API 키 테이블 (암호화 저장)"""
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # 암호화된 키 (Fernet 사용)
    encrypted_access_key = Column(Text, nullable=False, comment="암호화된 Access Key")
    encrypted_secret_key = Column(Text, nullable=False, comment="암호화된 Secret Key")
    
    # 키 메타데이터
    key_name = Column(String(100), nullable=True, comment="키 별칭 (사용자 지정)")
    is_active = Column(Boolean, default=True, nullable=False, comment="키 활성화 여부")
    last_validated_at = Column(DateTime(timezone=True), nullable=True, comment="마지막 검증 시각")
    
    # 권한 정보 (최소 권한 원칙)
    permissions = Column(Text, nullable=True, comment="키 권한 JSON (조회/거래만 허용)")
    
    # 타임스탬프
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # 관계
    user = relationship("User", back_populates="api_keys")


class AuditLogAction(str, enum.Enum):
    """감사 로그 액션"""
    LOGIN = "login"
    LOGOUT = "logout"
    REGISTER = "register"
    API_KEY_ADD = "api_key_add"
    API_KEY_DELETE = "api_key_delete"
    API_KEY_VALIDATE = "api_key_validate"
    TRADE_BUY = "trade_buy"
    TRADE_SELL = "trade_sell"
    SETTINGS_UPDATE = "settings_update"
    PASSWORD_CHANGE = "password_change"


class AuditLog(Base):
    """감사 로그 테이블 (보안/컴플라이언스)"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    
    # 액션 정보
    action = Column(SQLEnum(AuditLogAction), nullable=False, index=True, comment="수행 액션")
    resource = Column(String(100), nullable=True, comment="대상 리소스 (예: market, api_key)")
    resource_id = Column(String(100), nullable=True, comment="리소스 ID")
    
    # 상세 정보
    details = Column(Text, nullable=True, comment="액션 상세 (JSON)")
    ip_address = Column(String(45), nullable=True, comment="요청 IP 주소")
    user_agent = Column(String(500), nullable=True, comment="User Agent")
    
    # 결과
    success = Column(Boolean, default=True, nullable=False, comment="성공 여부")
    error_message = Column(Text, nullable=True, comment="에러 메시지 (실패 시)")
    
    # 타임스탬프
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # 관계
    user = relationship("User", back_populates="audit_logs")

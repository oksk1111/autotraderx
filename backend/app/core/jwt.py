"""
JWT 토큰 인증 시스템
- Access Token: 짧은 수명 (15분), API 인증용
- Refresh Token: 긴 수명 (7일), Access Token 갱신용
"""
from datetime import datetime, timedelta
from typing import Optional, Dict
from jose import JWTError, jwt
from pydantic import BaseModel
import os


class TokenData(BaseModel):
    """토큰 페이로드 데이터"""
    user_id: int
    email: str
    role: str


class JWTManager:
    """JWT 토큰 관리자"""
    
    def __init__(
        self,
        secret_key: str = None,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 15,
        refresh_token_expire_days: int = 7
    ):
        """
        Args:
            secret_key: JWT 서명 비밀키 (환경변수 JWT_SECRET_KEY 사용 권장)
            algorithm: JWT 알고리즘
            access_token_expire_minutes: Access Token 만료 시간 (분)
            refresh_token_expire_days: Refresh Token 만료 시간 (일)
        
        환경변수 설정:
            JWT_SECRET_KEY=랜덤_문자열_최소_32자
            
        키 생성 예:
            >>> import secrets
            >>> secrets.token_urlsafe(32)
        """
        self.secret_key = secret_key or os.getenv("JWT_SECRET_KEY")
        if not self.secret_key:
            raise ValueError(
                "JWT_SECRET_KEY 환경변수가 설정되지 않았습니다. "
                "secrets.token_urlsafe(32)로 키를 생성하고 .env에 추가하세요."
            )
        
        self.algorithm = algorithm
        self.access_token_expire_minutes = access_token_expire_minutes
        self.refresh_token_expire_days = refresh_token_expire_days
    
    def create_access_token(self, data: Dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        Access Token 생성
        
        Args:
            data: 토큰에 포함할 데이터 (user_id, email, role 등)
            expires_delta: 커스텀 만료 시간
        
        Returns:
            JWT 토큰 문자열
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({
            "exp": expire,
            "type": "access"
        })
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def create_refresh_token(self, data: Dict, expires_delta: Optional[timedelta] = None) -> str:
        """
        Refresh Token 생성
        
        Args:
            data: 토큰에 포함할 데이터
            expires_delta: 커스텀 만료 시간
        
        Returns:
            JWT 토큰 문자열
        """
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        
        to_encode.update({
            "exp": expire,
            "type": "refresh"
        })
        
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str, expected_type: str = "access") -> Optional[Dict]:
        """
        토큰 검증 및 페이로드 추출
        
        Args:
            token: JWT 토큰
            expected_type: 예상 토큰 타입 ("access" 또는 "refresh")
        
        Returns:
            토큰 페이로드 (dict) 또는 None (실패 시)
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            
            # 토큰 타입 검증
            token_type = payload.get("type")
            if token_type != expected_type:
                return None
            
            return payload
        
        except JWTError:
            return None
    
    def decode_token(self, token: str) -> Optional[TokenData]:
        """
        토큰을 TokenData 객체로 디코딩
        
        Args:
            token: JWT 토큰
        
        Returns:
            TokenData 객체 또는 None
        """
        payload = self.verify_token(token, expected_type="access")
        if not payload:
            return None
        
        try:
            return TokenData(
                user_id=payload.get("user_id"),
                email=payload.get("email"),
                role=payload.get("role")
            )
        except Exception:
            return None


# 전역 인스턴스
_jwt_manager = None

def get_jwt_manager() -> JWTManager:
    """JWT 관리자 싱글톤 인스턴스 반환"""
    global _jwt_manager
    if _jwt_manager is None:
        _jwt_manager = JWTManager()
    return _jwt_manager


def generate_jwt_secret() -> str:
    """
    JWT 비밀키 생성 (초기 설정용)
    
    Returns:
        URL-safe base64 인코딩된 랜덤 문자열
    """
    import secrets
    return secrets.token_urlsafe(32)

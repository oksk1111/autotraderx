"""
암호화 유틸리티
Upbit API 키를 Fernet (AES 대칭키) 방식으로 암호화/복호화
"""
from cryptography.fernet import Fernet
import os
import base64
from typing import Tuple


class EncryptionManager:
    """암호화 관리자"""
    
    def __init__(self, encryption_key: str = None):
        """
        Args:
            encryption_key: 암호화 키 (base64 인코딩된 32바이트 키)
                           None이면 환경변수 ENCRYPTION_KEY 사용
        
        환경변수 설정 방법:
            1. Python으로 키 생성:
               >>> from cryptography.fernet import Fernet
               >>> print(Fernet.generate_key().decode())
               
            2. .env 파일에 추가:
               ENCRYPTION_KEY=생성된_키_값
        """
        if encryption_key is None:
            encryption_key = os.getenv("ENCRYPTION_KEY")
            
        if not encryption_key:
            raise ValueError(
                "ENCRYPTION_KEY 환경변수가 설정되지 않았습니다. "
                "Fernet.generate_key()로 키를 생성하고 .env에 추가하세요."
            )
        
        # 문자열을 바이트로 변환
        if isinstance(encryption_key, str):
            encryption_key = encryption_key.encode()
        
        self.fernet = Fernet(encryption_key)
    
    def encrypt(self, plaintext: str) -> str:
        """
        평문을 암호화
        
        Args:
            plaintext: 암호화할 평문 (예: Upbit Access Key)
        
        Returns:
            암호화된 문자열 (base64 인코딩)
        """
        if not plaintext:
            raise ValueError("암호화할 텍스트가 비어있습니다.")
        
        encrypted_bytes = self.fernet.encrypt(plaintext.encode())
        return encrypted_bytes.decode()
    
    def decrypt(self, encrypted_text: str) -> str:
        """
        암호문을 복호화
        
        Args:
            encrypted_text: 암호화된 문자열
        
        Returns:
            복호화된 평문
        """
        if not encrypted_text:
            raise ValueError("복호화할 텍스트가 비어있습니다.")
        
        decrypted_bytes = self.fernet.decrypt(encrypted_text.encode())
        return decrypted_bytes.decode()
    
    def encrypt_api_keys(self, access_key: str, secret_key: str) -> Tuple[str, str]:
        """
        Upbit API 키 쌍을 암호화
        
        Args:
            access_key: Upbit Access Key
            secret_key: Upbit Secret Key
        
        Returns:
            (encrypted_access_key, encrypted_secret_key)
        """
        return (
            self.encrypt(access_key),
            self.encrypt(secret_key)
        )
    
    def decrypt_api_keys(self, encrypted_access: str, encrypted_secret: str) -> Tuple[str, str]:
        """
        암호화된 Upbit API 키 쌍을 복호화
        
        Args:
            encrypted_access: 암호화된 Access Key
            encrypted_secret: 암호화된 Secret Key
        
        Returns:
            (access_key, secret_key)
        """
        return (
            self.decrypt(encrypted_access),
            self.decrypt(encrypted_secret)
        )


def generate_encryption_key() -> str:
    """
    새로운 암호화 키 생성 (초기 설정용)
    
    Returns:
        base64 인코딩된 Fernet 키
    
    사용 예:
        >>> from app.core.encryption import generate_encryption_key
        >>> print(generate_encryption_key())
        # 생성된 키를 .env 파일에 ENCRYPTION_KEY=키값 형태로 저장
    """
    return Fernet.generate_key().decode()


# 전역 인스턴스 (환경변수 기반)
_encryption_manager = None

def get_encryption_manager() -> EncryptionManager:
    """암호화 관리자 싱글톤 인스턴스 반환"""
    global _encryption_manager
    if _encryption_manager is None:
        _encryption_manager = EncryptionManager()
    return _encryption_manager

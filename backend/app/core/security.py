from cryptography.fernet import Fernet
from app.core.config import settings
import base64
import hashlib


class SecurityManager:
    """Security manager for encryption/decryption"""
    
    def __init__(self):
        # Generate Fernet key from settings
        key = hashlib.sha256(settings.ENCRYPTION_KEY.encode()).digest()
        self.cipher = Fernet(base64.urlsafe_b64encode(key))
    
    def encrypt(self, data: str) -> str:
        """Encrypt data"""
        return self.cipher.encrypt(data.encode()).decode()
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt data"""
        return self.cipher.decrypt(encrypted_data.encode()).decode()


security_manager = SecurityManager()

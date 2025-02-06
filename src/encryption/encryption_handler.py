import base64
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger(__name__)

class EncryptionHandler:
    def __init__(self, key: str):
        """Initialize the encryption handler with a key."""
        # Convert the key to bytes and ensure it's valid for Fernet
        key_bytes = base64.b64encode(key.encode()[:32].ljust(32, b'\0'))
        self.fernet = Fernet(key_bytes)
        
    def encrypt(self, data: bytes) -> bytes:
        """Encrypt the given data."""
        try:
            return self.fernet.encrypt(data)
        except Exception as e:
            logging.error(f"Encryption failed: {e}")
            
            
    def decrypt(self, encrypted_data: bytes) -> bytes:
        """Decrypt the given data."""
        try:
            return self.fernet.decrypt(encrypted_data)
        except Exception as e:
            logging.error(f"Decryption failed: {e}")
            

# Make sure to export the class
__all__ = ['EncryptionHandler'] 
import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import keyring

class KeyManager:
    def __init__(self, app_name: str = "backup_tool"):
        self.app_name = app_name
        self.service_name = f"{app_name}_encryption"

    def generate_key(self, password: str) -> bytes:
        """Generate a new encryption key from password"""
        salt = os.urandom(16)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key

    def store_key(self, key: bytes):
        """Store encryption key securely"""
        keyring.set_password(
            self.service_name,
            "encryption_key",
            key.decode()
        )

    def get_key(self) -> bytes:
        """Retrieve stored encryption key"""
        key = keyring.get_password(self.service_name, "encryption_key")
        if not key:
            KeyError("No encryption key found")
        return key.encode()

    def create_fernet(self) -> Fernet:
        """Create Fernet instance with stored key"""
        return Fernet(self.get_key()) 
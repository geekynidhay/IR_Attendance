"""
Encryption Utilities for IR Attendance
Handles symmetric encryption of image files for secure distribution.
"""
import io
import os
from cryptography.fernet import Fernet
from pathlib import Path

class EncryptionUtils:
    """Utility class for image encryption and decryption"""
    
    EXTENSION = ".ira"  # IR Attendance Secure Format
    
    @staticmethod
    def generate_key():
        """Generate a new Fernet key"""
        return Fernet.generate_key()
    
    @staticmethod
    def encrypt_file(source_path, target_path, key):
        """Encrypt a file and save to target path"""
        try:
            f = Fernet(key)
            with open(source_path, 'rb') as file:
                file_data = file.read()
            
            encrypted_data = f.encrypt(file_data)
            
            # Create directories if needed
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            
            with open(target_path, 'wb') as file:
                file.write(encrypted_data)
            return True
        except Exception as e:
            print(f"Encryption failed: {e}")
            return False
            
    @staticmethod
    def decrypt_to_bytes(source_path, key):
        """Decrypt a file and return as bytes (for PIL)"""
        try:
            f = Fernet(key)
            with open(source_path, 'rb') as file:
                encrypted_data = file.read()
            
            decrypted_data = f.decrypt(encrypted_data)
            return decrypted_data
        except Exception as e:
            print(f"Decryption failed: {e}")
            return None

    @staticmethod
    def is_encrypted(file_path):
        """Check if file has the secure extension"""
        return Path(file_path).suffix.lower() == EncryptionUtils.EXTENSION

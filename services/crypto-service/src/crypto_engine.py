"""
Cryptographic Engine Module

Implements AES-256-GCM encryption with PBKDF2 key derivation
for secure tactical message encryption.
"""

import os
import base64

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import structlog

logger = structlog.get_logger()

# Cryptographic constants
NONCE_SIZE = 12  # 96 bits for GCM
KEY_SIZE = 32    # 256 bits
SALT_SIZE = 16   # 128 bits
PBKDF2_ITERATIONS = 100000


class CryptoEngine:
    """
    AES-256-GCM encryption engine with PBKDF2 key derivation.

    Security properties:
    - Confidentiality: AES-256 encryption
    - Integrity: GCM authentication tag
    - Key derivation: PBKDF2 with 100k iterations
    """

    def __init__(self, master_key: str):
        """
        Initialize crypto engine with master key.

        Args:
            master_key: Master key for key derivation
        """
        self.master_key = master_key.encode('utf-8')
        logger.info("Crypto engine initialized")

    def _derive_key(self, salt: bytes) -> bytes:
        """
        Derive encryption key using PBKDF2-SHA256.

        Args:
            salt: Random salt for key derivation

        Returns:
            32-byte derived key
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KEY_SIZE,
            salt=salt,
            iterations=PBKDF2_ITERATIONS,
        )
        return kdf.derive(self.master_key)

    def encrypt(self, plaintext: str) -> dict:
        """
        Encrypt plaintext using AES-256-GCM.

        Args:
            plaintext: Message to encrypt

        Returns:
            dict with ciphertext, nonce, and tag (all base64 encoded)
        """
        # Generate random salt and nonce
        salt = os.urandom(SALT_SIZE)
        nonce = os.urandom(NONCE_SIZE)

        # Derive key
        key = self._derive_key(salt)

        # Encrypt with AES-GCM
        aesgcm = AESGCM(key)
        plaintext_bytes = plaintext.encode('utf-8')

        # GCM returns ciphertext with tag appended
        ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext_bytes, None)

        # Split ciphertext and tag (last 16 bytes)
        ciphertext = ciphertext_with_tag[:-16]
        tag = ciphertext_with_tag[-16:]

        # Prepend salt to ciphertext for decryption
        ciphertext_with_salt = salt + ciphertext

        return {
            "ciphertext": base64.b64encode(ciphertext_with_salt).decode('utf-8'),
            "nonce": base64.b64encode(nonce).decode('utf-8'),
            "tag": base64.b64encode(tag).decode('utf-8')
        }

    def decrypt(self, ciphertext: str, nonce: str, tag: str) -> str:
        """
        Decrypt ciphertext using AES-256-GCM.

        Args:
            ciphertext: Base64 encoded ciphertext (with salt prepended)
            nonce: Base64 encoded nonce
            tag: Base64 encoded authentication tag

        Returns:
            Decrypted plaintext

        Raises:
            ValueError: If authentication fails
        """
        # Decode base64
        ciphertext_with_salt = base64.b64decode(ciphertext)
        nonce_bytes = base64.b64decode(nonce)
        tag_bytes = base64.b64decode(tag)

        # Extract salt and ciphertext
        salt = ciphertext_with_salt[:SALT_SIZE]
        ciphertext_bytes = ciphertext_with_salt[SALT_SIZE:]

        # Derive key
        key = self._derive_key(salt)

        # Reconstruct ciphertext with tag for decryption
        ciphertext_with_tag = ciphertext_bytes + tag_bytes

        # Decrypt with AES-GCM
        aesgcm = AESGCM(key)

        try:
            plaintext_bytes = aesgcm.decrypt(nonce_bytes, ciphertext_with_tag, None)
            return plaintext_bytes.decode('utf-8')
        except Exception as e:
            logger.warning("Decryption failed - authentication error")
            raise ValueError("Message authentication failed") from e

    def verify(self, ciphertext: str, nonce: str, tag: str) -> bool:
        """
        Verify message integrity without returning plaintext.

        Args:
            ciphertext: Base64 encoded ciphertext
            nonce: Base64 encoded nonce
            tag: Base64 encoded authentication tag

        Returns:
            True if integrity check passes
        """
        try:
            self.decrypt(ciphertext, nonce, tag)
            return True
        except ValueError:
            return False
        except Exception as e:
            logger.error("Verification error", error=str(e))
            return False

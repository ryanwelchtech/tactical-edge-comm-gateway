"""
Unit tests for Crypto Service.
"""

import pytest
import base64
import sys
import os

# Add service to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'crypto-service'))


class TestCryptoEngine:
    """Tests for CryptoEngine class."""
    
    @pytest.fixture
    def crypto_engine(self):
        """Create CryptoEngine instance."""
        from src.crypto_engine import CryptoEngine
        return CryptoEngine("test-master-key-for-testing")
    
    def test_encrypt_returns_required_fields(self, crypto_engine):
        """Test that encryption returns all required fields."""
        plaintext = "Test message for encryption"
        result = crypto_engine.encrypt(plaintext)
        
        assert "ciphertext" in result
        assert "nonce" in result
        assert "tag" in result
    
    def test_encrypt_produces_base64_output(self, crypto_engine):
        """Test that encryption output is base64 encoded."""
        plaintext = "Test message"
        result = crypto_engine.encrypt(plaintext)
        
        # Should not raise exception if valid base64
        base64.b64decode(result["ciphertext"])
        base64.b64decode(result["nonce"])
        base64.b64decode(result["tag"])
    
    def test_encrypt_decrypt_roundtrip(self, crypto_engine):
        """Test that encryption followed by decryption returns original plaintext."""
        original = "Top Secret: Test message with special chars: @#$%^&*()"
        
        encrypted = crypto_engine.encrypt(original)
        decrypted = crypto_engine.decrypt(
            ciphertext=encrypted["ciphertext"],
            nonce=encrypted["nonce"],
            tag=encrypted["tag"]
        )
        
        assert decrypted == original
    
    def test_different_messages_produce_different_ciphertext(self, crypto_engine):
        """Test that different messages produce different ciphertext."""
        result1 = crypto_engine.encrypt("Message 1")
        result2 = crypto_engine.encrypt("Message 2")
        
        assert result1["ciphertext"] != result2["ciphertext"]
    
    def test_same_message_produces_different_ciphertext(self, crypto_engine):
        """Test that same message encrypted twice produces different ciphertext (due to random nonce)."""
        message = "Same message"
        result1 = crypto_engine.encrypt(message)
        result2 = crypto_engine.encrypt(message)
        
        assert result1["ciphertext"] != result2["ciphertext"]
        assert result1["nonce"] != result2["nonce"]
    
    def test_tampered_ciphertext_fails_verification(self, crypto_engine):
        """Test that tampered ciphertext fails verification."""
        original = "Original message"
        encrypted = crypto_engine.encrypt(original)
        
        # Tamper with ciphertext
        ciphertext_bytes = base64.b64decode(encrypted["ciphertext"])
        tampered = bytearray(ciphertext_bytes)
        tampered[20] ^= 0xFF  # Flip bits
        tampered_b64 = base64.b64encode(bytes(tampered)).decode('utf-8')
        
        with pytest.raises(ValueError):
            crypto_engine.decrypt(
                ciphertext=tampered_b64,
                nonce=encrypted["nonce"],
                tag=encrypted["tag"]
            )
    
    def test_verify_valid_ciphertext(self, crypto_engine):
        """Test verification of valid ciphertext."""
        message = "Valid message"
        encrypted = crypto_engine.encrypt(message)
        
        is_valid = crypto_engine.verify(
            ciphertext=encrypted["ciphertext"],
            nonce=encrypted["nonce"],
            tag=encrypted["tag"]
        )
        
        assert is_valid is True
    
    def test_verify_invalid_ciphertext(self, crypto_engine):
        """Test verification of invalid ciphertext."""
        message = "Valid message"
        encrypted = crypto_engine.encrypt(message)
        
        # Use wrong tag
        wrong_tag = base64.b64encode(b"wrong-tag-value!").decode('utf-8')
        
        is_valid = crypto_engine.verify(
            ciphertext=encrypted["ciphertext"],
            nonce=encrypted["nonce"],
            tag=wrong_tag
        )
        
        assert is_valid is False


class TestCryptoConstants:
    """Tests for cryptographic constants."""
    
    def test_nonce_size(self):
        """Test nonce size is 12 bytes (96 bits) for GCM."""
        from src.crypto_engine import NONCE_SIZE
        assert NONCE_SIZE == 12
    
    def test_key_size(self):
        """Test key size is 32 bytes (256 bits)."""
        from src.crypto_engine import KEY_SIZE
        assert KEY_SIZE == 32
    
    def test_salt_size(self):
        """Test salt size is 16 bytes (128 bits)."""
        from src.crypto_engine import SALT_SIZE
        assert SALT_SIZE == 16
    
    def test_pbkdf2_iterations(self):
        """Test PBKDF2 iterations is at least 100,000."""
        from src.crypto_engine import PBKDF2_ITERATIONS
        assert PBKDF2_ITERATIONS >= 100000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


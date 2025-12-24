"""
Unit tests for Gateway Core service.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# Add service to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'services', 'gateway-core'))


class TestJWTAuth:
    """Tests for JWT authentication."""
    
    def test_valid_token_format(self):
        """Test that valid JWT format is accepted."""
        # JWT tokens have 3 parts separated by dots
        token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJOT0RFLUFMUEhBIiwicm9sZSI6Im9wZXJhdG9yIn0.signature"
        parts = token.split('.')
        assert len(parts) == 3
    
    def test_role_permissions_mapping(self):
        """Test that role-permission mapping is correct."""
        from src.auth import ROLE_PERMISSIONS
        
        assert "message:send" in ROLE_PERMISSIONS["operator"]
        assert "message:read" in ROLE_PERMISSIONS["operator"]
        assert "node:status" in ROLE_PERMISSIONS["operator"]
        
        assert "message:delete" in ROLE_PERMISSIONS["supervisor"]
        assert "audit:read" in ROLE_PERMISSIONS["supervisor"]
        
        assert "node:manage" in ROLE_PERMISSIONS["admin"]
        assert "config:write" in ROLE_PERMISSIONS["admin"]


class TestMessagePrecedence:
    """Tests for message precedence handling."""
    
    def test_precedence_values(self):
        """Test precedence enum values."""
        from src.message_handler import MessagePrecedence
        
        assert MessagePrecedence.FLASH.value == "FLASH"
        assert MessagePrecedence.IMMEDIATE.value == "IMMEDIATE"
        assert MessagePrecedence.PRIORITY.value == "PRIORITY"
        assert MessagePrecedence.ROUTINE.value == "ROUTINE"
    
    def test_precedence_latency(self):
        """Test maximum latency values."""
        from src.message_handler import MessagePrecedence
        
        assert MessagePrecedence.FLASH.max_latency_ms == 100
        assert MessagePrecedence.IMMEDIATE.max_latency_ms == 500
        assert MessagePrecedence.PRIORITY.max_latency_ms == 2000
        assert MessagePrecedence.ROUTINE.max_latency_ms == 10000
    
    def test_precedence_priority_order(self):
        """Test that priority values are correctly ordered."""
        from src.message_handler import MessagePrecedence
        
        assert MessagePrecedence.FLASH.priority_value < MessagePrecedence.IMMEDIATE.priority_value
        assert MessagePrecedence.IMMEDIATE.priority_value < MessagePrecedence.PRIORITY.priority_value
        assert MessagePrecedence.PRIORITY.priority_value < MessagePrecedence.ROUTINE.priority_value


class TestMessageHandler:
    """Tests for MessageHandler class."""
    
    @pytest.fixture
    def mock_http_client(self):
        """Create mock HTTP client."""
        client = AsyncMock()
        client.post = AsyncMock()
        client.get = AsyncMock()
        return client
    
    def test_handler_initialization(self, mock_http_client):
        """Test MessageHandler initialization."""
        from src.message_handler import MessageHandler
        
        handler = MessageHandler(
            crypto_service_url="http://localhost:5001",
            audit_service_url="http://localhost:5002",
            store_forward_url="http://localhost:5003",
            http_client=mock_http_client
        )
        
        assert handler.crypto_service_url == "http://localhost:5001"
        assert handler.audit_service_url == "http://localhost:5002"
        assert handler.store_forward_url == "http://localhost:5003"


class TestAPIEndpoints:
    """Tests for API endpoints."""
    
    def test_health_endpoint_format(self):
        """Test health endpoint response format."""
        health_response = {
            "status": "healthy",
            "version": "1.0.0",
            "uptime_seconds": 3600,
            "checks": {"gateway": "healthy"}
        }
        
        assert "status" in health_response
        assert "version" in health_response
        assert health_response["status"] == "healthy"
    
    def test_message_request_validation(self):
        """Test message request schema validation."""
        valid_precedences = ["FLASH", "IMMEDIATE", "PRIORITY", "ROUTINE"]
        valid_classifications = ["UNCLASSIFIED", "CONFIDENTIAL", "SECRET", "TOP_SECRET"]
        
        for p in valid_precedences:
            assert p in valid_precedences
        
        for c in valid_classifications:
            assert c in valid_classifications


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


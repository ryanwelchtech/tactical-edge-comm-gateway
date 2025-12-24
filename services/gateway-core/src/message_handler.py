"""
Message Handler Module

Handles message routing, precedence classification, and coordination
with downstream services (crypto, audit, store-forward).
"""

from enum import Enum
from datetime import datetime, timezone, timedelta
from typing import Optional
from dataclasses import dataclass

import httpx
import structlog

logger = structlog.get_logger()


class MessagePrecedence(Enum):
    """Military-standard message precedence levels."""
    FLASH = "FLASH"           # Immediate threat/engagement
    IMMEDIATE = "IMMEDIATE"   # Time-critical operations
    PRIORITY = "PRIORITY"     # Urgent operational traffic
    ROUTINE = "ROUTINE"       # Administrative/logistics

    @property
    def max_latency_ms(self) -> int:
        """Maximum acceptable latency in milliseconds."""
        latency_map = {
            "FLASH": 100,
            "IMMEDIATE": 500,
            "PRIORITY": 2000,
            "ROUTINE": 10000
        }
        return latency_map.get(self.value, 10000)

    @property
    def priority_value(self) -> int:
        """Numeric priority for queue ordering (lower = higher priority)."""
        priority_map = {
            "FLASH": 1,
            "IMMEDIATE": 2,
            "PRIORITY": 3,
            "ROUTINE": 4
        }
        return priority_map.get(self.value, 4)


@dataclass
class ProcessedMessage:
    """Result of message processing."""
    message_id: str
    status: str
    encrypted_content: Optional[str] = None
    estimated_delivery: Optional[str] = None
    error: Optional[str] = None


class MessageHandler:
    """
    Orchestrates message processing through the gateway pipeline.

    Pipeline:
    1. Encrypt message content via Crypto Service
    2. Log event via Audit Service
    3. Route to destination or queue in Store-Forward
    """

    def __init__(
        self,
        crypto_service_url: str,
        audit_service_url: str,
        store_forward_url: str,
        http_client: httpx.AsyncClient
    ):
        self.crypto_service_url = crypto_service_url
        self.audit_service_url = audit_service_url
        self.store_forward_url = store_forward_url
        self.http_client = http_client

        # Simulated node registry
        self.connected_nodes = {"NODE-ALPHA", "NODE-BRAVO"}

    async def process_message(
        self,
        message_id: str,
        precedence: MessagePrecedence,
        classification: str,
        sender: str,
        recipient: str,
        content: str,
        ttl: int,
        jwt_token: str
    ) -> dict:
        """
        Process a tactical message through the gateway pipeline.

        Args:
            message_id: Unique message identifier
            precedence: Message priority level
            classification: Security classification
            sender: Sender node ID
            recipient: Recipient node ID
            content: Message content
            ttl: Time-to-live in seconds
            jwt_token: JWT token for downstream authentication

        Returns:
            dict with status and metadata
        """
        headers = {"Authorization": f"Bearer {jwt_token}"}

        # Step 1: Encrypt message content
        encrypted_content = await self._encrypt_content(content, classification, headers)

        # Step 2: Log audit event
        await self._log_audit_event(
            message_id=message_id,
            event_type="MESSAGE_SENT",
            precedence=precedence.value,
            classification=classification,
            sender=sender,
            recipient=recipient,
            headers=headers
        )

        # Step 3: Route message
        if recipient in self.connected_nodes:
            # Direct delivery
            status = await self._deliver_message(
                message_id=message_id,
                recipient=recipient,
                encrypted_content=encrypted_content,
                precedence=precedence,
                headers=headers
            )
        else:
            # Queue for store-forward
            status = await self._queue_message(
                message_id=message_id,
                recipient=recipient,
                encrypted_content=encrypted_content,
                precedence=precedence,
                ttl=ttl,
                headers=headers
            )

        # Calculate estimated delivery
        estimated_delivery = None
        if status == "QUEUED" or status == "TRANSMITTED":
            delivery_time = datetime.now(timezone.utc) + timedelta(milliseconds=precedence.max_latency_ms)
            estimated_delivery = delivery_time.isoformat()

        return {
            "status": status,
            "estimated_delivery": estimated_delivery
        }

    async def _encrypt_content(
        self,
        content: str,
        classification: str,
        headers: dict
    ) -> str:
        """Encrypt message content via Crypto Service."""
        try:
            response = await self.http_client.post(
                f"{self.crypto_service_url}/api/v1/encrypt",
                json={
                    "plaintext": content,
                    "classification": classification
                },
                headers=headers,
                timeout=5.0
            )

            if response.status_code == 200:
                data = response.json()
                logger.debug("Message encrypted successfully")
                return data.get("ciphertext", content)
            else:
                logger.warning(
                    "Crypto service returned error",
                    status_code=response.status_code
                )
                # Fallback: return original content (not recommended in production)
                return content

        except httpx.RequestError as e:
            logger.error("Crypto service unavailable", error=str(e))
            # In production, this should fail the request
            # For demo, we continue with unencrypted content
            return content

    async def _log_audit_event(
        self,
        message_id: str,
        event_type: str,
        precedence: str,
        classification: str,
        sender: str,
        recipient: str,
        headers: dict
    ) -> None:
        """Log audit event via Audit Service."""
        try:
            await self.http_client.post(
                f"{self.audit_service_url}/api/v1/audit/events",
                json={
                    "event_type": event_type,
                    "control_family": "AU",
                    "actor": {
                        "node_id": sender,
                        "role": "operator"
                    },
                    "action": {
                        "operation": "SEND_MESSAGE",
                        "resource": f"message:{message_id}",
                        "outcome": "SUCCESS"
                    },
                    "context": {
                        "precedence": precedence,
                        "classification": classification,
                        "recipient": recipient
                    }
                },
                headers=headers,
                timeout=2.0
            )
            logger.debug("Audit event logged", event_type=event_type)

        except httpx.RequestError as e:
            # Audit logging failure should not block message processing
            # but should be alerted on
            logger.warning("Audit service unavailable", error=str(e))

    async def _deliver_message(
        self,
        message_id: str,
        recipient: str,
        encrypted_content: str,
        precedence: MessagePrecedence,
        headers: dict
    ) -> str:
        """Attempt direct delivery to connected node."""
        # In production, this would connect to the actual tactical node
        # For demo, we simulate successful delivery
        logger.info(
            "Message delivered",
            message_id=message_id,
            recipient=recipient,
            precedence=precedence.value
        )
        return "TRANSMITTED"

    async def _queue_message(
        self,
        message_id: str,
        recipient: str,
        encrypted_content: str,
        precedence: MessagePrecedence,
        ttl: int,
        headers: dict
    ) -> str:
        """Queue message for store-forward delivery."""
        try:
            response = await self.http_client.post(
                f"{self.store_forward_url}/api/v1/queue/enqueue",
                json={
                    "message_id": message_id,
                    "recipient": recipient,
                    "encrypted_content": encrypted_content,
                    "precedence": precedence.value,
                    "ttl": ttl
                },
                headers=headers,
                timeout=5.0
            )

            if response.status_code in (200, 201):
                logger.info(
                    "Message queued for store-forward",
                    message_id=message_id,
                    recipient=recipient,
                    precedence=precedence.value
                )
                return "STORED"
            else:
                logger.warning(
                    "Store-forward service returned error",
                    status_code=response.status_code
                )
                return "QUEUED"

        except httpx.RequestError as e:
            logger.error("Store-forward service unavailable", error=str(e))
            return "QUEUED"

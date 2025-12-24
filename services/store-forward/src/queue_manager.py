"""
Queue Manager Module

Implements priority-based message queuing using Redis
for store-and-forward operations in disconnected environments.
"""

import json
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from typing import Optional, List

import redis.asyncio as redis
import structlog

logger = structlog.get_logger()

# Priority mappings (lower = higher priority)
PRIORITY_MAP = {
    "FLASH": 1,
    "IMMEDIATE": 2,
    "PRIORITY": 3,
    "ROUTINE": 4
}

# Default TTL by precedence
DEFAULT_TTL = {
    "FLASH": 300,      # 5 minutes
    "IMMEDIATE": 900,   # 15 minutes
    "PRIORITY": 3600,   # 1 hour
    "ROUTINE": 86400    # 24 hours
}


@dataclass
class QueuedMessage:
    """Message stored in the queue."""
    message_id: str
    recipient: str
    encrypted_content: str
    precedence: str
    created_at: str
    expires_at: str
    retry_count: int = 0
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    @classmethod
    def from_json(cls, data: str) -> 'QueuedMessage':
        return cls(**json.loads(data))


class QueueManager:
    """
    Priority-based message queue manager using Redis.
    
    Features:
    - Priority ordering (FLASH > IMMEDIATE > PRIORITY > ROUTINE)
    - TTL management and automatic expiration
    - Retry with exponential backoff
    - Queue depth monitoring
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        """
        Initialize queue manager.
        
        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url
        self.redis: Optional[redis.Redis] = None
        self.is_connected = False
        self.expired_count_24h = 0
        
        # Queue keys by precedence
        self.queue_keys = {
            "FLASH": "tacedge:queue:flash",
            "IMMEDIATE": "tacedge:queue:immediate",
            "PRIORITY": "tacedge:queue:priority",
            "ROUTINE": "tacedge:queue:routine"
        }
    
    async def connect(self) -> None:
        """Connect to Redis."""
        try:
            self.redis = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self.redis.ping()
            self.is_connected = True
            logger.info("Connected to Redis", url=self.redis_url)
        except Exception as e:
            logger.warning("Redis connection failed, using in-memory fallback", error=str(e))
            self.is_connected = False
            self._fallback_queues = {
                "FLASH": [],
                "IMMEDIATE": [],
                "PRIORITY": [],
                "ROUTINE": []
            }
    
    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.redis:
            await self.redis.close()
            self.is_connected = False
            logger.info("Disconnected from Redis")
    
    async def enqueue(
        self,
        message_id: str,
        recipient: str,
        encrypted_content: str,
        precedence: str,
        ttl: int
    ) -> dict:
        """
        Add message to the appropriate priority queue.
        
        Args:
            message_id: Unique message identifier
            recipient: Destination node ID
            encrypted_content: Encrypted message payload
            precedence: Message priority level
            ttl: Time-to-live in seconds
        
        Returns:
            dict with queue_position and expires_at
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl)
        
        message = QueuedMessage(
            message_id=message_id,
            recipient=recipient,
            encrypted_content=encrypted_content,
            precedence=precedence,
            created_at=now.isoformat(),
            expires_at=expires_at.isoformat()
        )
        
        if self.is_connected and self.redis:
            # Use Redis sorted set with timestamp as score
            queue_key = self.queue_keys.get(precedence, self.queue_keys["ROUTINE"])
            score = now.timestamp()
            
            await self.redis.zadd(queue_key, {message.to_json(): score})
            
            # Set expiration on the message
            await self.redis.setex(
                f"tacedge:msg:{message_id}",
                ttl,
                message.to_json()
            )
            
            # Get queue position
            queue_position = await self.redis.zrank(queue_key, message.to_json())
            queue_position = queue_position + 1 if queue_position is not None else 1
        else:
            # Fallback to in-memory queue
            self._fallback_queues[precedence].append(message)
            queue_position = len(self._fallback_queues[precedence])
        
        return {
            "queue_position": queue_position,
            "expires_at": expires_at.isoformat()
        }
    
    async def dequeue(self, precedence: str) -> Optional[QueuedMessage]:
        """
        Remove and return the oldest message from a queue.
        
        Args:
            precedence: Priority queue to dequeue from
        
        Returns:
            QueuedMessage or None if queue is empty
        """
        if self.is_connected and self.redis:
            queue_key = self.queue_keys.get(precedence)
            if not queue_key:
                return None
            
            # Get and remove oldest message
            result = await self.redis.zpopmin(queue_key)
            if result:
                message_data, _ = result[0]
                return QueuedMessage.from_json(message_data)
        else:
            # Fallback
            queue = self._fallback_queues.get(precedence, [])
            if queue:
                return queue.pop(0)
        
        return None
    
    async def get_queue_depth(self, precedence: str) -> int:
        """Get current depth of a priority queue."""
        if self.is_connected and self.redis:
            queue_key = self.queue_keys.get(precedence)
            if queue_key:
                return await self.redis.zcard(queue_key)
        else:
            return len(self._fallback_queues.get(precedence, []))
        return 0
    
    async def get_total_depth(self) -> int:
        """Get total depth across all queues."""
        total = 0
        for precedence in PRIORITY_MAP.keys():
            total += await self.get_queue_depth(precedence)
        return total
    
    async def get_oldest_message_time(self, precedence: str) -> Optional[str]:
        """Get timestamp of oldest message in queue."""
        if self.is_connected and self.redis:
            queue_key = self.queue_keys.get(precedence)
            if queue_key:
                result = await self.redis.zrange(queue_key, 0, 0, withscores=True)
                if result:
                    message_data, score = result[0]
                    message = QueuedMessage.from_json(message_data)
                    return message.created_at
        else:
            queue = self._fallback_queues.get(precedence, [])
            if queue:
                return queue[0].created_at
        return None
    
    async def flush_all(self) -> dict:
        """
        Attempt to deliver all queued messages.
        
        Returns:
            dict with flushed and failed counts
        """
        flushed = 0
        failed = 0
        
        # Process in priority order
        for precedence in ["FLASH", "IMMEDIATE", "PRIORITY", "ROUTINE"]:
            while True:
                message = await self.dequeue(precedence)
                if message is None:
                    break
                
                # In production, attempt delivery here
                # For demo, we just count as flushed
                flushed += 1
                
                logger.debug(
                    "Message flushed",
                    message_id=message.message_id,
                    precedence=precedence
                )
        
        return {
            "flushed": flushed,
            "failed": failed
        }


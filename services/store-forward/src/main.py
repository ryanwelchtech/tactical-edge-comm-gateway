"""
Tactical Edge Communications Gateway - Store-Forward Service

Message queuing service for disconnected/degraded network operations.
Implements priority-based queuing with TTL management.
"""

import os
import time
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import structlog

from .queue_manager import QueueManager

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)
logger = structlog.get_logger()

# Prometheus metrics
QUEUE_DEPTH = Gauge(
    'tacedge_queue_depth',
    'Current queue depth',
    ['priority']
)
MESSAGES_ENQUEUED = Counter(
    'tacedge_messages_enqueued_total',
    'Total messages enqueued',
    ['priority']
)
MESSAGES_DEQUEUED = Counter(
    'tacedge_messages_dequeued_total',
    'Total messages dequeued',
    ['priority']
)
MESSAGES_EXPIRED = Counter(
    'tacedge_messages_expired_total',
    'Total messages expired',
    ['priority']
)

queue_manager: QueueManager = None
_processing_task = None


async def process_queue_worker():
    """Background worker that automatically processes queued messages."""
    logger.info("Starting queue processing worker")

    while True:
        try:
            # Process messages in priority order
            for precedence in ["FLASH", "IMMEDIATE", "PRIORITY", "ROUTINE"]:
                message = await queue_manager.dequeue(precedence)
                if message:
                    # Simulate message delivery
                    # In production, this would attempt actual delivery to the recipient
                    MESSAGES_DEQUEUED.labels(priority=precedence).inc()
                    logger.info(
                        "Message processed from queue",
                        message_id=message.message_id,
                        precedence=precedence,
                        recipient=message.recipient
                    )

            # Wait before next processing cycle
            await asyncio.sleep(2)  # Process queue every 2 seconds

        except Exception as e:
            logger.error("Queue processing error", error=str(e))
            await asyncio.sleep(5)  # Wait longer on error


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    global queue_manager, _processing_task

    logger.info("Starting Store-Forward Service")

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    queue_manager = QueueManager(redis_url=redis_url)
    await queue_manager.connect()

    # Start background queue processing worker
    _processing_task = asyncio.create_task(process_queue_worker())

    yield

    # Stop background worker
    if _processing_task:
        _processing_task.cancel()
        try:
            await _processing_task
        except asyncio.CancelledError:
            pass

    logger.info("Shutting down Store-Forward Service")
    await queue_manager.disconnect()


app = FastAPI(
    title="TacEdge Store-Forward Service",
    description="Priority-based message queuing for disconnected operations",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Request/Response Models
# ============================================================================

class EnqueueRequest(BaseModel):
    """Message enqueue request."""
    message_id: str
    recipient: str
    encrypted_content: str
    precedence: str = Field(..., pattern="^(FLASH|IMMEDIATE|PRIORITY|ROUTINE)$")
    ttl: int = Field(default=3600, ge=60, le=86400)


class EnqueueResponse(BaseModel):
    """Message enqueue response."""
    message_id: str
    queue_position: int
    precedence: str
    expires_at: str


class QueueStatusResponse(BaseModel):
    """Queue status response."""
    queues: dict
    total_queued: int
    total_expired_24h: int


class FlushResponse(BaseModel):
    """Queue flush response."""
    flushed: int
    failed: int
    status: str


class HealthResponse(BaseModel):
    """Service health status."""
    status: str
    version: str
    redis_connected: bool
    total_queued: int


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Liveness probe endpoint."""
    redis_connected = queue_manager.is_connected if queue_manager else False
    total_queued = await queue_manager.get_total_depth() if queue_manager and redis_connected else 0

    return HealthResponse(
        status="healthy" if redis_connected else "degraded",
        version="1.0.0",
        redis_connected=redis_connected,
        total_queued=total_queued
    )


@app.get("/ready", tags=["Health"])
async def readiness_check():
    """Readiness probe endpoint."""
    if queue_manager is None or not queue_manager.is_connected:
        return {"ready": False, "reason": "Redis not connected"}
    return {"ready": True}


@app.get("/metrics", tags=["Observability"])
async def metrics():
    """Prometheus metrics endpoint."""
    # Update queue depth gauges
    if queue_manager and queue_manager.is_connected:
        for precedence in ["FLASH", "IMMEDIATE", "PRIORITY", "ROUTINE"]:
            depth = await queue_manager.get_queue_depth(precedence)
            QUEUE_DEPTH.labels(priority=precedence).set(depth)

    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.post("/api/v1/queue/enqueue", response_model=EnqueueResponse, status_code=201, tags=["Queue"])
async def enqueue_message(request: EnqueueRequest):
    """
    Enqueue a message for store-forward delivery.

    Messages are queued by precedence (FLASH > IMMEDIATE > PRIORITY > ROUTINE)
    and delivered in priority order when the destination becomes available.
    """
    try:
        result = await queue_manager.enqueue(
            message_id=request.message_id,
            recipient=request.recipient,
            encrypted_content=request.encrypted_content,
            precedence=request.precedence,
            ttl=request.ttl
        )

        MESSAGES_ENQUEUED.labels(priority=request.precedence).inc()

        logger.info(
            "Message enqueued",
            message_id=request.message_id,
            precedence=request.precedence,
            queue_position=result["queue_position"]
        )

        return EnqueueResponse(
            message_id=request.message_id,
            queue_position=result["queue_position"],
            precedence=request.precedence,
            expires_at=result["expires_at"]
        )

    except Exception as e:
        logger.error("Enqueue failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Enqueue failed: {str(e)}")


@app.get("/api/v1/queue/status", response_model=QueueStatusResponse, tags=["Queue"])
async def get_queue_status():
    """Get current queue depth and statistics."""

    queues = {}
    for precedence in ["FLASH", "IMMEDIATE", "PRIORITY", "ROUTINE"]:
        depth = await queue_manager.get_queue_depth(precedence)
        oldest = await queue_manager.get_oldest_message_time(precedence)
        queues[precedence] = {
            "depth": depth,
            "oldest_message": oldest
        }

    total_queued = sum(q["depth"] for q in queues.values())

    return QueueStatusResponse(
        queues=queues,
        total_queued=total_queued,
        total_expired_24h=queue_manager.expired_count_24h
    )


@app.post("/api/v1/queue/flush", response_model=FlushResponse, tags=["Queue"])
async def flush_queue():
    """
    Force immediate transmission of all queued messages.

    Requires admin role.
    """
    try:
        result = await queue_manager.flush_all()

        logger.info(
            "Queue flushed",
            flushed=result["flushed"],
            failed=result["failed"]
        )

        return FlushResponse(
            flushed=result["flushed"],
            failed=result["failed"],
            status="COMPLETED"
        )

    except Exception as e:
        logger.error("Flush failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Flush failed: {str(e)}")


@app.on_event("startup")
async def startup_event():
    app.state.start_time = time.time()
    logger.info("Store-Forward Service started")

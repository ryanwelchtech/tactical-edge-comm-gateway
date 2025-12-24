"""
Tactical Edge Communications Gateway - Core Service

This service handles message routing, precedence classification,
and orchestration of the tactical communications platform.
"""

import os
import uuid
import time
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Optional

import httpx
import structlog
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from .auth import JWTClaims, require_permission
from .message_handler import MessageHandler, MessagePrecedence

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
MESSAGES_TOTAL = Counter(
    'tacedge_messages_total',
    'Total messages processed',
    ['precedence', 'status']
)
MESSAGE_LATENCY = Histogram(
    'tacedge_message_latency_seconds',
    'Message processing latency',
    ['precedence'],
    buckets=[.01, .025, .05, .1, .25, .5, 1.0, 2.5, 5.0]
)
AUTH_FAILURES = Counter(
    'tacedge_auth_failures_total',
    'Authentication failures',
    ['reason']
)

# Service clients
message_handler: Optional[MessageHandler] = None
http_client: Optional[httpx.AsyncClient] = None

# In-memory message store (in production, use persistent storage)
message_store: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    global message_handler, http_client

    # Startup
    logger.info("Starting Gateway Core service")
    http_client = httpx.AsyncClient(timeout=30.0)
    message_handler = MessageHandler(
        crypto_service_url=os.getenv("CRYPTO_SERVICE_URL", "http://localhost:5001"),
        audit_service_url=os.getenv("AUDIT_SERVICE_URL", "http://localhost:5002"),
        store_forward_url=os.getenv("STORE_FORWARD_URL", "http://localhost:5003"),
        http_client=http_client
    )

    yield

    # Shutdown
    logger.info("Shutting down Gateway Core service")
    await http_client.aclose()


app = FastAPI(
    title="Tactical Edge Communications Gateway",
    description="Zero Trust tactical message routing platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
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

class MessageRequest(BaseModel):
    """Incoming tactical message request."""
    precedence: str = Field(..., pattern="^(FLASH|IMMEDIATE|PRIORITY|ROUTINE)$")
    classification: str = Field(..., pattern="^(UNCLASSIFIED|CONFIDENTIAL|SECRET|TOP_SECRET)$")
    sender: str = Field(..., min_length=1, max_length=64)
    recipient: str = Field(..., min_length=1, max_length=64)
    content: str = Field(..., min_length=1, max_length=65536)
    ttl: int = Field(default=3600, ge=60, le=86400)


class MessageResponse(BaseModel):
    """Message submission response."""
    message_id: str
    status: str
    precedence: str
    created_at: str
    estimated_delivery: Optional[str] = None


class MessageStatusResponse(BaseModel):
    """Message status response."""
    message_id: str
    status: str
    precedence: str
    sender: str
    recipient: str
    created_at: str
    delivered_at: Optional[str] = None
    latency_ms: Optional[int] = None
    encrypted: bool = True
    audit_trail: list = []


class NodeInfo(BaseModel):
    """Tactical node information."""
    node_id: str
    status: str
    last_seen: str
    ip_address: str
    capabilities: list[str]


class NodesResponse(BaseModel):
    """List of registered nodes."""
    nodes: list[NodeInfo]
    total: int
    connected: int
    disconnected: int


class HealthResponse(BaseModel):
    """Service health status."""
    status: str
    version: str
    uptime_seconds: int
    checks: dict


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Liveness probe endpoint."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        uptime_seconds=int(time.time() - app.state.start_time if hasattr(app.state, 'start_time') else 0),
        checks={
            "gateway": "healthy"
        }
    )


@app.get("/ready", tags=["Health"])
async def readiness_check():
    """Readiness probe endpoint."""
    # Check downstream service connectivity
    checks = {}
    all_healthy = True

    try:
        if http_client:
            # Check crypto service
            try:
                resp = await http_client.get(
                    f"{os.getenv('CRYPTO_SERVICE_URL', 'http://localhost:5001')}/health"
                )
                checks["crypto_service"] = "healthy" if resp.status_code == 200 else "unhealthy"
            except Exception:
                checks["crypto_service"] = "unavailable"
                all_healthy = False

            # Check audit service
            try:
                resp = await http_client.get(
                    f"{os.getenv('AUDIT_SERVICE_URL', 'http://localhost:5002')}/health"
                )
                checks["audit_service"] = "healthy" if resp.status_code == 200 else "unhealthy"
            except Exception:
                checks["audit_service"] = "unavailable"
                # Audit unavailable is not critical for readiness
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))

    return {"ready": all_healthy, "checks": checks}


@app.get("/metrics", tags=["Observability"])
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.post("/api/v1/messages", response_model=MessageResponse, status_code=201, tags=["Messages"])
async def send_message(
    request: MessageRequest,
    claims: JWTClaims = Depends(require_permission("message:send"))
):
    """
    Send a tactical message with specified precedence.

    Message precedence levels:
    - FLASH: Immediate threat/engagement (< 100ms)
    - IMMEDIATE: Time-critical operations (< 500ms)
    - PRIORITY: Urgent operational traffic (< 2s)
    - ROUTINE: Administrative/logistics (best effort)
    """
    start_time = time.time()
    message_id = f"msg-{uuid.uuid4()}"

    logger.info(
        "Received message",
        message_id=message_id,
        precedence=request.precedence,
        sender=request.sender,
        recipient=request.recipient,
        node_id=claims.node_id
    )

    try:
        # Store message content for retrieval
        message_store[message_id] = {
            "message_id": message_id,
            "precedence": request.precedence,
            "classification": request.classification,
            "sender": request.sender,
            "recipient": request.recipient,
            "content": request.content,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "PENDING"
        }

        # Process message through handler
        result = await message_handler.process_message(
            message_id=message_id,
            precedence=MessagePrecedence(request.precedence),
            classification=request.classification,
            sender=request.sender,
            recipient=request.recipient,
            content=request.content,
            ttl=request.ttl,
            jwt_token=claims.raw_token
        )

        # Update stored message status
        if message_id in message_store:
            message_store[message_id]["status"] = result["status"]
            message_store[message_id]["estimated_delivery"] = result.get("estimated_delivery")

        # Calculate latency and record metrics
        latency = time.time() - start_time
        MESSAGE_LATENCY.labels(precedence=request.precedence).observe(latency)
        MESSAGES_TOTAL.labels(precedence=request.precedence, status=result["status"]).inc()

        logger.info(
            "Message processed",
            message_id=message_id,
            status=result["status"],
            latency_ms=int(latency * 1000)
        )

        return MessageResponse(
            message_id=message_id,
            status=result["status"],
            precedence=request.precedence,
            created_at=datetime.now(timezone.utc).isoformat(),
            estimated_delivery=result.get("estimated_delivery")
        )

    except Exception as e:
        MESSAGES_TOTAL.labels(precedence=request.precedence, status="FAILED").inc()
        logger.error("Message processing failed", message_id=message_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Message processing failed: {str(e)}")


@app.get("/api/v1/messages/{message_id}", response_model=MessageStatusResponse, tags=["Messages"])
async def get_message_status(
    message_id: str,
    claims: JWTClaims = Depends(require_permission("message:read"))
):
    """Retrieve the status of a previously sent message."""
    
    # Check message store first
    if message_id in message_store:
        msg = message_store[message_id]
        return MessageStatusResponse(
            message_id=msg["message_id"],
            status=msg["status"],
            precedence=msg["precedence"],
            sender=msg["sender"],
            recipient=msg["recipient"],
            created_at=msg["created_at"],
            delivered_at=msg.get("estimated_delivery"),
            latency_ms=None,
            encrypted=True,
            audit_trail=[]
        )
    
    # Fallback for demo
    raise HTTPException(status_code=404, detail="Message not found")


@app.get("/api/v1/messages/{message_id}/content", tags=["Messages"])
async def get_message_content(
    message_id: str,
    claims: JWTClaims = Depends(require_permission("message:read"))
):
    """Retrieve the content of a previously sent message."""
    
    if message_id in message_store:
        msg = message_store[message_id]
        return {
            "message_id": message_id,
            "content": msg["content"],
            "precedence": msg["precedence"],
            "classification": msg["classification"],
            "sender": msg["sender"],
            "recipient": msg["recipient"]
        }
    
    raise HTTPException(status_code=404, detail="Message not found")


@app.post("/api/v1/messages/{message_id}/ack", tags=["Messages"])
async def acknowledge_message(
    message_id: str,
    claims: JWTClaims = Depends(require_permission("message:read"))
):
    """Acknowledge receipt of a message."""

    logger.info(
        "Message acknowledged",
        message_id=message_id,
        acknowledged_by=claims.node_id
    )

    return {
        "message_id": message_id,
        "acknowledged": True,
        "acknowledged_at": datetime.now(timezone.utc).isoformat(),
        "acknowledged_by": claims.node_id
    }


@app.get("/api/v1/nodes", response_model=NodesResponse, tags=["Nodes"])
async def list_nodes(
    claims: JWTClaims = Depends(require_permission("node:status"))
):
    """List all registered tactical nodes and their status."""

    # Simulated node list for demo
    nodes = [
        NodeInfo(
            node_id="NODE-ALPHA",
            status="CONNECTED",
            last_seen=datetime.now(timezone.utc).isoformat(),
            ip_address="10.0.1.50",
            capabilities=["FLASH", "IMMEDIATE", "PRIORITY", "ROUTINE"]
        ),
        NodeInfo(
            node_id="NODE-BRAVO",
            status="CONNECTED",
            last_seen=datetime.now(timezone.utc).isoformat(),
            ip_address="10.0.1.51",
            capabilities=["FLASH", "IMMEDIATE", "PRIORITY", "ROUTINE"]
        ),
        NodeInfo(
            node_id="NODE-CHARLIE",
            status="CONNECTED",
            last_seen=datetime.now(timezone.utc).isoformat(),
            ip_address="10.0.1.52",
            capabilities=["FLASH", "IMMEDIATE", "PRIORITY", "ROUTINE"]
        ),
        NodeInfo(
            node_id="NODE-DELTA",
            status="CONNECTED",
            last_seen=datetime.now(timezone.utc).isoformat(),
            ip_address="10.0.1.53",
            capabilities=["FLASH", "IMMEDIATE", "PRIORITY", "ROUTINE"]
        )
    ]

    connected = sum(1 for n in nodes if n.status == "CONNECTED")

    return NodesResponse(
        nodes=nodes,
        total=len(nodes),
        connected=connected,
        disconnected=len(nodes) - connected
    )


# Initialize start time for uptime tracking
@app.on_event("startup")
async def startup_event():
    app.state.start_time = time.time()
    logger.info("Gateway Core started", start_time=app.state.start_time)

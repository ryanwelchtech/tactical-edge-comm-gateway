"""
Audit Service - NIST 800-53 Compliant Audit Logging

This service provides centralized audit logging for the
Tactical Edge Communications Gateway platform.
"""

import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import structlog

from .audit_logger import AuditLogger, AuditActor, AuditAction

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
AUDIT_EVENTS = Counter(
    'tacedge_audit_events_total',
    'Total audit events recorded',
    ['event_type', 'control_family']
)

# Global audit logger instance
audit_logger: Optional[AuditLogger] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    global audit_logger

    logger.info("Starting Audit Service")
    audit_logger = AuditLogger()

    yield

    logger.info("Shutting down Audit Service")


app = FastAPI(
    title="TacEdge Audit Service",
    description="NIST 800-53 compliant audit logging service",
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

class ActorModel(BaseModel):
    """Actor information."""
    node_id: str
    role: str
    ip_address: Optional[str] = None
    session_id: Optional[str] = None


class ActionModel(BaseModel):
    """Action information."""
    operation: str
    resource: str
    outcome: str = "SUCCESS"
    reason: Optional[str] = None


class AuditEventRequest(BaseModel):
    """Request to create an audit event."""
    event_type: str = Field(..., description="Type of event")
    control_family: str = Field(..., pattern="^(AC|AU|IA|SC|SI)$")
    actor: ActorModel
    action: ActionModel
    context: dict = Field(default_factory=dict)


class AuditEventResponse(BaseModel):
    """Response for a created audit event."""
    event_id: str
    timestamp: str
    event_type: str
    control_family: str
    actor: ActorModel
    action: ActionModel
    context: dict
    hash: str


class AuditEventsListResponse(BaseModel):
    """Response for listing audit events."""
    events: list[dict]
    total: int
    filtered: int


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    events_stored: int


# ============================================================================
# Helper Functions
# ============================================================================

def verify_token(authorization: str = Header(None)) -> dict:
    """Simple token verification for service-to-service auth."""
    # In production, implement full JWT verification
    if authorization and authorization.startswith("Bearer "):
        return {"authenticated": True}
    return {"authenticated": False}


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Liveness probe endpoint."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        events_stored=len(audit_logger.events) if audit_logger else 0
    )


@app.get("/ready", tags=["Health"])
async def readiness_check():
    """Readiness probe endpoint."""
    return {"ready": audit_logger is not None}


@app.get("/metrics", tags=["Observability"])
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.post("/api/v1/audit/events", response_model=AuditEventResponse, status_code=201, tags=["Audit"])
async def create_audit_event(
    request: AuditEventRequest,
    auth: dict = Depends(verify_token)
):
    """
    Record an audit event.

    Implements NIST 800-53 AU-2 (Audit Events) and AU-3 (Content of Audit Records).
    """
    event_id = f"evt-{uuid.uuid4()}"

    actor = AuditActor(
        node_id=request.actor.node_id,
        role=request.actor.role,
        ip_address=request.actor.ip_address,
        session_id=request.actor.session_id
    )

    action = AuditAction(
        operation=request.action.operation,
        resource=request.action.resource,
        outcome=request.action.outcome,
        reason=request.action.reason
    )

    event = audit_logger.log_event(
        event_id=event_id,
        event_type=request.event_type,
        control_family=request.control_family,
        actor=actor,
        action=action,
        context=request.context
    )

    AUDIT_EVENTS.labels(
        event_type=request.event_type,
        control_family=request.control_family
    ).inc()

    return AuditEventResponse(
        event_id=event.event_id,
        timestamp=event.timestamp,
        event_type=event.event_type,
        control_family=event.control_family,
        actor=request.actor,
        action=request.action,
        context=event.context,
        hash=event.hash
    )


@app.get("/api/v1/audit/events", response_model=AuditEventsListResponse, tags=["Audit"])
async def list_audit_events(
    event_type: Optional[str] = None,
    control_family: Optional[str] = None,
    actor_node: Optional[str] = None,
    limit: int = 100,
    auth: dict = Depends(verify_token)
):
    """
    Query audit events with optional filters.

    Implements NIST 800-53 AU-6 (Audit Review, Analysis, and Reporting).
    """
    events = audit_logger.get_events(
        event_type=event_type,
        control_family=control_family,
        actor_node=actor_node,
        limit=limit
    )

    return AuditEventsListResponse(
        events=[e.to_dict() for e in events],
        total=len(audit_logger.events),
        filtered=len(events)
    )


@app.get("/api/v1/audit/export", tags=["Audit"])
async def export_audit_log(
    format: str = "json",
    auth: dict = Depends(verify_token)
):
    """
    Export audit log for external analysis.

    Implements NIST 800-53 AU-6 (Audit Review, Analysis, and Reporting).
    """
    export_data = audit_logger.export_events(format=format)

    return Response(
        content=export_data,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=audit-export-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"}
    )

"""
Tactical Edge Communications Gateway - Audit Service

NIST 800-53 compliant security event logging service.
Maps audit events to control families: AC, AU, IA, SC, SI.
"""

import os
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import structlog

from .audit_logger import AuditLogger, AuditEvent

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
AUDIT_EVENTS_TOTAL = Counter(
    'tacedge_audit_events_total',
    'Total audit events logged',
    ['control_family', 'event_type', 'outcome']
)

audit_logger: AuditLogger = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    global audit_logger
    
    logger.info("Starting Audit Service")
    audit_logger = AuditLogger(
        storage_path=os.getenv("AUDIT_STORAGE_PATH", "/app/data")
    )
    
    yield
    
    logger.info("Shutting down Audit Service")


app = FastAPI(
    title="TacEdge Audit Service",
    description="NIST 800-53 compliant security event logging",
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

class ActorInfo(BaseModel):
    """Actor information for audit event."""
    node_id: str
    role: str = "operator"
    ip_address: Optional[str] = None


class ActionInfo(BaseModel):
    """Action information for audit event."""
    operation: str
    resource: str
    outcome: str = "SUCCESS"


class ContextInfo(BaseModel):
    """Additional context for audit event."""
    precedence: Optional[str] = None
    classification: Optional[str] = None
    recipient: Optional[str] = None


class AuditEventRequest(BaseModel):
    """Audit event creation request."""
    event_type: str
    control_family: str = Field(..., pattern="^(AC|AU|IA|SC|SI)$")
    actor: ActorInfo
    action: ActionInfo
    context: Optional[ContextInfo] = None


class AuditEventResponse(BaseModel):
    """Audit event response."""
    event_id: str
    timestamp: str
    control_family: str
    event_type: str
    actor: dict
    action: dict
    context: Optional[dict] = None


class AuditEventsListResponse(BaseModel):
    """List of audit events."""
    events: List[AuditEventResponse]
    total: int
    page: int
    limit: int


class AuditStatsResponse(BaseModel):
    """Audit statistics."""
    period: str
    total_events: int
    by_control_family: dict
    by_outcome: dict
    top_actors: List[dict]


class HealthResponse(BaseModel):
    """Service health status."""
    status: str
    version: str
    events_logged: int


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Liveness probe endpoint."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        events_logged=audit_logger.event_count if audit_logger else 0
    )


@app.get("/ready", tags=["Health"])
async def readiness_check():
    """Readiness probe endpoint."""
    if audit_logger is None:
        return {"ready": False, "reason": "Audit logger not initialized"}
    return {"ready": True}


@app.get("/metrics", tags=["Observability"])
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.post("/api/v1/audit/events", response_model=AuditEventResponse, status_code=201, tags=["Audit"])
async def create_audit_event(request: AuditEventRequest):
    """
    Create a new audit event.
    
    Control families:
    - AC: Access Control
    - AU: Audit and Accountability
    - IA: Identification and Authentication
    - SC: System and Communications Protection
    - SI: System and Information Integrity
    """
    event_id = f"evt-{uuid.uuid4()}"
    timestamp = datetime.now(timezone.utc).isoformat()
    
    # Create audit event
    event = AuditEvent(
        event_id=event_id,
        timestamp=timestamp,
        control_family=request.control_family,
        event_type=request.event_type,
        actor=request.actor.model_dump(),
        action=request.action.model_dump(),
        context=request.context.model_dump() if request.context else {}
    )
    
    # Log event
    audit_logger.log_event(event)
    
    # Update metrics
    AUDIT_EVENTS_TOTAL.labels(
        control_family=request.control_family,
        event_type=request.event_type,
        outcome=request.action.outcome
    ).inc()
    
    logger.info(
        "Audit event created",
        event_id=event_id,
        control_family=request.control_family,
        event_type=request.event_type
    )
    
    return AuditEventResponse(
        event_id=event_id,
        timestamp=timestamp,
        control_family=request.control_family,
        event_type=request.event_type,
        actor=request.actor.model_dump(),
        action=request.action.model_dump(),
        context=request.context.model_dump() if request.context else None
    )


@app.get("/api/v1/audit/events", response_model=AuditEventsListResponse, tags=["Audit"])
async def query_audit_events(
    control_family: Optional[str] = Query(None, pattern="^(AC|AU|IA|SC|SI)$"),
    event_type: Optional[str] = None,
    node_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    page: int = Query(1, ge=1)
):
    """
    Query audit events with optional filters.
    
    Implements NIST 800-53 AU-6 (Audit Review, Analysis, and Reporting)
    """
    events = audit_logger.query_events(
        control_family=control_family,
        event_type=event_type,
        node_id=node_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
        offset=(page - 1) * limit
    )
    
    event_responses = [
        AuditEventResponse(
            event_id=e.event_id,
            timestamp=e.timestamp,
            control_family=e.control_family,
            event_type=e.event_type,
            actor=e.actor,
            action=e.action,
            context=e.context if e.context else None
        )
        for e in events
    ]
    
    return AuditEventsListResponse(
        events=event_responses,
        total=len(events),
        page=page,
        limit=limit
    )


@app.get("/api/v1/audit/stats", response_model=AuditStatsResponse, tags=["Audit"])
async def get_audit_stats():
    """
    Get aggregated audit statistics for the last 24 hours.
    """
    stats = audit_logger.get_stats()
    
    return AuditStatsResponse(
        period="24h",
        total_events=stats["total_events"],
        by_control_family=stats["by_control_family"],
        by_outcome=stats["by_outcome"],
        top_actors=stats["top_actors"]
    )


@app.on_event("startup")
async def startup_event():
    app.state.start_time = time.time()
    logger.info("Audit Service started")


"""
NIST 800-53 Compliant Audit Logger

Implements structured audit logging aligned with:
- AU-2: Audit Events
- AU-3: Content of Audit Records
- AU-6: Audit Review, Analysis, and Reporting
- AU-9: Protection of Audit Information
"""

import json
import hashlib
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, field, asdict
from enum import Enum

import structlog

logger = structlog.get_logger()


class ControlFamily(Enum):
    """NIST 800-53 Control Families relevant to this system."""
    AC = "Access Control"
    AU = "Audit and Accountability"
    IA = "Identification and Authentication"
    SC = "System and Communications Protection"
    SI = "System and Information Integrity"


class EventOutcome(Enum):
    """Standard event outcomes."""
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    UNKNOWN = "UNKNOWN"


@dataclass
class AuditActor:
    """Actor performing the audited action."""
    node_id: str
    role: str
    ip_address: Optional[str] = None
    session_id: Optional[str] = None


@dataclass
class AuditAction:
    """Details of the audited action."""
    operation: str
    resource: str
    outcome: str
    reason: Optional[str] = None


@dataclass
class AuditEvent:
    """
    Complete audit event record.

    Implements AU-3 required fields:
    - Type of event
    - When the event occurred
    - Where the event occurred
    - Source of the event
    - Outcome of the event
    - Identity of individuals/subjects associated with the event
    """
    event_id: str
    timestamp: str
    event_type: str
    control_family: str
    actor: AuditActor
    action: AuditAction
    context: dict = field(default_factory=dict)
    hash: Optional[str] = None

    def __post_init__(self):
        """Generate integrity hash after initialization."""
        if not self.hash:
            self.hash = self._generate_hash()

    def _generate_hash(self) -> str:
        """Generate SHA-256 hash of the event for integrity verification."""
        event_data = {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "control_family": self.control_family,
            "actor": asdict(self.actor),
            "action": asdict(self.action),
            "context": self.context
        }
        event_json = json.dumps(event_data, sort_keys=True)
        return hashlib.sha256(event_json.encode()).hexdigest()

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "control_family": self.control_family,
            "actor": asdict(self.actor),
            "action": asdict(self.action),
            "context": self.context,
            "hash": self.hash
        }


class AuditLogger:
    """
    NIST 800-53 compliant audit logger.

    Provides structured logging for security-relevant events
    with integrity protection and tamper detection.
    """

    def __init__(self):
        self.events: list[AuditEvent] = []
        self.max_events = 10000  # In production, use persistent storage

    def log_event(
        self,
        event_id: str,
        event_type: str,
        control_family: str,
        actor: AuditActor,
        action: AuditAction,
        context: Optional[dict] = None
    ) -> AuditEvent:
        """
        Log an audit event.

        Args:
            event_id: Unique event identifier
            event_type: Type of event (e.g., MESSAGE_SENT, AUTH_SUCCESS)
            control_family: NIST 800-53 control family
            actor: Actor performing the action
            action: Details of the action
            context: Additional context information

        Returns:
            The created AuditEvent
        """
        event = AuditEvent(
            event_id=event_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            control_family=control_family,
            actor=actor,
            action=action,
            context=context or {}
        )

        # Store event (in production, persist to secure storage)
        self.events.append(event)

        # Maintain max events limit
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]

        # Log to structured logger
        logger.info(
            "Audit event recorded",
            event_id=event.event_id,
            event_type=event.event_type,
            control_family=event.control_family,
            actor_node=actor.node_id,
            action_operation=action.operation,
            action_outcome=action.outcome
        )

        return event

    def get_events(
        self,
        event_type: Optional[str] = None,
        control_family: Optional[str] = None,
        actor_node: Optional[str] = None,
        limit: int = 100
    ) -> list[AuditEvent]:
        """
        Query audit events with optional filters.

        Args:
            event_type: Filter by event type
            control_family: Filter by control family
            actor_node: Filter by actor node ID
            limit: Maximum number of events to return

        Returns:
            List of matching AuditEvents
        """
        filtered = self.events

        if event_type:
            filtered = [e for e in filtered if e.event_type == event_type]

        if control_family:
            filtered = [e for e in filtered if e.control_family == control_family]

        if actor_node:
            filtered = [e for e in filtered if e.actor.node_id == actor_node]

        # Return most recent events first
        return sorted(filtered, key=lambda e: e.timestamp, reverse=True)[:limit]

    def verify_integrity(self, event: AuditEvent) -> bool:
        """
        Verify the integrity of an audit event.

        Implements AU-9 protection of audit information.

        Args:
            event: The event to verify

        Returns:
            True if integrity check passes
        """
        original_hash = event.hash
        event.hash = None
        computed_hash = event._generate_hash()
        event.hash = original_hash

        return original_hash == computed_hash

    def export_events(self, format: str = "json") -> str:
        """
        Export audit events for analysis.

        Implements AU-6 audit review and reporting.

        Args:
            format: Export format (currently only 'json' supported)

        Returns:
            Serialized audit events
        """
        events_data = [e.to_dict() for e in self.events]
        return json.dumps(events_data, indent=2)

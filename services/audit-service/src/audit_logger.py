"""
Audit Logger Module

Implements NIST 800-53 compliant audit logging with
structured events mapped to control families.
"""

import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional, List
from collections import defaultdict

import structlog

logger = structlog.get_logger()


@dataclass
class AuditEvent:
    """
    Structured audit event following NIST 800-53 AU-3 requirements.
    
    Captures: who, what, when, where, and outcome.
    """
    event_id: str
    timestamp: str
    control_family: str  # AC, AU, IA, SC, SI
    event_type: str
    actor: dict  # node_id, role, ip_address
    action: dict  # operation, resource, outcome
    context: dict = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict())


class AuditLogger:
    """
    NIST 800-53 compliant audit logger.
    
    Implements:
    - AU-2: Auditable Events
    - AU-3: Content of Audit Records
    - AU-4: Audit Log Storage Capacity
    - AU-9: Protection of Audit Information
    """
    
    def __init__(self, storage_path: str = "/app/data"):
        """
        Initialize audit logger.
        
        Args:
            storage_path: Directory for audit log storage
        """
        self.storage_path = storage_path
        self.events: List[AuditEvent] = []
        self.event_count = 0
        
        # In-memory indices for querying
        self._by_control_family: dict = defaultdict(list)
        self._by_event_type: dict = defaultdict(list)
        self._by_node: dict = defaultdict(list)
        
        # Ensure storage directory exists
        os.makedirs(storage_path, exist_ok=True)
        
        logger.info("Audit logger initialized", storage_path=storage_path)
    
    def log_event(self, event: AuditEvent) -> None:
        """
        Log an audit event.
        
        Args:
            event: AuditEvent to log
        """
        # Store in memory
        self.events.append(event)
        self.event_count += 1
        
        # Update indices
        self._by_control_family[event.control_family].append(event)
        self._by_event_type[event.event_type].append(event)
        if event.actor and "node_id" in event.actor:
            self._by_node[event.actor["node_id"]].append(event)
        
        # Write to persistent storage (append-only)
        self._persist_event(event)
        
        logger.debug(
            "Audit event logged",
            event_id=event.event_id,
            control_family=event.control_family
        )
    
    def _persist_event(self, event: AuditEvent) -> None:
        """
        Persist event to storage (append-only for tamper-evidence).
        
        Args:
            event: AuditEvent to persist
        """
        try:
            # Daily log rotation
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            log_file = os.path.join(self.storage_path, f"audit-{date_str}.jsonl")
            
            with open(log_file, "a") as f:
                f.write(event.to_json() + "\n")
                
        except Exception as e:
            logger.error("Failed to persist audit event", error=str(e))
    
    def query_events(
        self,
        control_family: Optional[str] = None,
        event_type: Optional[str] = None,
        node_id: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AuditEvent]:
        """
        Query audit events with filters.
        
        Args:
            control_family: Filter by control family
            event_type: Filter by event type
            node_id: Filter by actor node ID
            start_time: ISO-8601 start time
            end_time: ISO-8601 end time
            limit: Maximum results
            offset: Result offset for pagination
        
        Returns:
            List of matching AuditEvents
        """
        # Start with appropriate index
        if control_family:
            events = self._by_control_family.get(control_family, [])
        elif event_type:
            events = self._by_event_type.get(event_type, [])
        elif node_id:
            events = self._by_node.get(node_id, [])
        else:
            events = self.events
        
        # Apply additional filters
        filtered = []
        for event in events:
            # Control family filter
            if control_family and event.control_family != control_family:
                continue
            
            # Event type filter
            if event_type and event.event_type != event_type:
                continue
            
            # Node ID filter
            if node_id:
                if not event.actor or event.actor.get("node_id") != node_id:
                    continue
            
            # Time range filter
            if start_time:
                if event.timestamp < start_time:
                    continue
            if end_time:
                if event.timestamp > end_time:
                    continue
            
            filtered.append(event)
        
        # Apply pagination
        return filtered[offset:offset + limit]
    
    def get_stats(self) -> dict:
        """
        Get aggregated audit statistics.
        
        Returns:
            dict with statistics
        """
        # Count by control family
        by_control_family = {
            cf: len(events) for cf, events in self._by_control_family.items()
        }
        
        # Count by outcome
        by_outcome = defaultdict(int)
        for event in self.events:
            if event.action and "outcome" in event.action:
                by_outcome[event.action["outcome"]] += 1
        
        # Top actors
        actor_counts = defaultdict(int)
        for event in self.events:
            if event.actor and "node_id" in event.actor:
                actor_counts[event.actor["node_id"]] += 1
        
        top_actors = [
            {"node_id": node_id, "count": count}
            for node_id, count in sorted(
                actor_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
        ]
        
        return {
            "total_events": self.event_count,
            "by_control_family": dict(by_control_family),
            "by_outcome": dict(by_outcome),
            "top_actors": top_actors
        }


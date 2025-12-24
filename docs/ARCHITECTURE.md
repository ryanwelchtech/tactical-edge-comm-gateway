# System Architecture

## Overview

The Tactical Edge Communications Gateway (TacEdge-Gateway) is a distributed microservices platform designed for secure tactical message routing in contested environments. The architecture prioritizes:

1. **Zero Trust Security** - No implicit trust between services
2. **Resilience** - Graceful degradation during network partitions
3. **Compliance** - NIST 800-53 control implementation
4. **Observability** - Comprehensive metrics and audit logging

---

## Component Architecture

### Service Decomposition

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              TACEDGE GATEWAY PLATFORM                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   ┌─────────────────┐                                                           │
│   │  GATEWAY-CORE   │◄── Primary ingress point                                  │
│   │   Port: 5000    │    JWT validation, routing, precedence handling           │
│   └────────┬────────┘                                                           │
│            │                                                                     │
│   ┌────────┴────────┬──────────────────┬───────────────────┐                   │
│   │                 │                  │                   │                   │
│   ▼                 ▼                  ▼                   ▼                   │
│ ┌───────────┐  ┌───────────┐  ┌─────────────┐  ┌───────────────────┐          │
│ │  CRYPTO   │  │  AUDIT    │  │ STORE-FWD   │  │    DASHBOARD      │          │
│ │  SERVICE  │  │  SERVICE  │  │   SERVICE   │  │    (Frontend)     │          │
│ │ Port:5001 │  │ Port:5002 │  │  Port:5003  │  │    Port: 8080     │          │
│ └───────────┘  └───────────┘  └──────┬──────┘  └───────────────────┘          │
│                                      │                                          │
│                                      ▼                                          │
│                              ┌──────────────┐                                   │
│                              │    REDIS     │                                   │
│                              │  Port: 6379  │                                   │
│                              └──────────────┘                                   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Service Descriptions

### 1. Gateway Core (`gateway-core`)

**Purpose**: Central message routing and orchestration service

**Responsibilities**:
- JWT token validation and claims extraction
- Message precedence classification and prioritization
- Request routing to downstream services
- Rate limiting and throttling
- Health aggregation

**Key Endpoints**:
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/messages` | POST | Submit new message |
| `/api/v1/messages/{id}` | GET | Retrieve message status |
| `/api/v1/messages/{id}/ack` | POST | Acknowledge delivery |
| `/api/v1/nodes` | GET | List registered nodes |
| `/health` | GET | Liveness check |
| `/ready` | GET | Readiness check |

**Precedence Queue Architecture**:
```
┌─────────────────────────────────────────────────┐
│              GATEWAY CORE QUEUES                │
├─────────────────────────────────────────────────┤
│  ┌─────────┐  Priority: FLASH (P1)              │
│  │ █████   │  Max Latency: 100ms                │
│  └─────────┘                                    │
│  ┌─────────┐  Priority: IMMEDIATE (P2)          │
│  │ ████    │  Max Latency: 500ms                │
│  └─────────┘                                    │
│  ┌─────────┐  Priority: PRIORITY (P3)           │
│  │ ███     │  Max Latency: 2s                   │
│  └─────────┘                                    │
│  ┌─────────┐  Priority: ROUTINE (P4)            │
│  │ ██      │  Max Latency: Best Effort          │
│  └─────────┘                                    │
└─────────────────────────────────────────────────┘
```

---

### 2. Crypto Service (`crypto-service`)

**Purpose**: Centralized encryption and decryption operations

**Responsibilities**:
- AES-256-GCM message encryption
- Key derivation (PBKDF2-SHA256)
- Message integrity verification (HMAC-SHA256)
- Key rotation support

**Cryptographic Operations**:
```
ENCRYPTION FLOW:
┌─────────┐     ┌─────────────┐     ┌─────────────┐
│Plaintext│────►│ PBKDF2 Key  │────►│ AES-256-GCM │────► Ciphertext
│ Message │     │ Derivation  │     │  Encrypt    │
└─────────┘     └─────────────┘     └─────────────┘
                      │
                      ▼
              ┌─────────────┐
              │ HMAC-SHA256 │────► Integrity Tag
              │  Signature  │
              └─────────────┘
```

**Key Endpoints**:
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/encrypt` | POST | Encrypt message payload |
| `/api/v1/decrypt` | POST | Decrypt message payload |
| `/api/v1/verify` | POST | Verify message integrity |

---

### 3. Audit Service (`audit-service`)

**Purpose**: NIST 800-53 compliant security event logging

**Responsibilities**:
- Structured audit event capture
- Control family classification
- Tamper-evident log storage
- Audit event querying

**Audit Event Schema**:
```json
{
  "event_id": "uuid",
  "timestamp": "ISO-8601",
  "control_family": "AU|AC|IA|SC|SI",
  "event_type": "AUTH_SUCCESS|AUTH_FAILURE|MESSAGE_SENT|...",
  "actor": {
    "node_id": "NODE-ALPHA",
    "role": "operator",
    "ip_address": "10.0.1.50"
  },
  "action": {
    "operation": "SEND_MESSAGE",
    "resource": "message:12345",
    "outcome": "SUCCESS"
  },
  "context": {
    "precedence": "FLASH",
    "classification": "UNCLASSIFIED"
  }
}
```

**Control Family Mapping**:
| Control | Event Types |
|---------|-------------|
| AC (Access Control) | RBAC_CHECK, PERMISSION_DENIED |
| AU (Audit) | AUDIT_START, AUDIT_EXPORT |
| IA (Identification) | AUTH_SUCCESS, AUTH_FAILURE, TOKEN_REFRESH |
| SC (System Protection) | ENCRYPT, DECRYPT, KEY_ROTATE |
| SI (System Integrity) | INTEGRITY_CHECK, TAMPER_DETECTED |

---

### 4. Store-Forward Service (`store-forward`)

**Purpose**: Message queuing for disconnected/degraded network operations

**Responsibilities**:
- Priority-based message queuing
- TTL management and expiration
- Delivery retry with exponential backoff
- Queue depth monitoring

**Queue Architecture**:
```
┌─────────────────────────────────────────────────────────────┐
│                    STORE-FORWARD SERVICE                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌─────────────────┐         ┌─────────────────┐           │
│   │  INBOUND QUEUE  │────────►│  REDIS CLUSTER  │           │
│   │  (Receiving)    │         │  (Persistence)  │           │
│   └─────────────────┘         └────────┬────────┘           │
│                                        │                     │
│   ┌────────────────────────────────────┼─────────────────┐  │
│   │                                    │                 │  │
│   ▼                                    ▼                 ▼  │
│ ┌──────────┐                    ┌──────────┐      ┌──────────┐
│ │ FLASH Q  │  Priority: 1       │ IMMED Q  │  P:2 │ PRIOR Q  │ P:3
│ │ TTL: 5m  │                    │ TTL: 15m │      │ TTL: 1h  │
│ └──────────┘                    └──────────┘      └──────────┘
│                                                              │
│   OUTBOUND DISPATCHER (Priority-ordered transmission)        │
│   ┌──────────────────────────────────────────────────────┐  │
│   │  FLASH ──► IMMEDIATE ──► PRIORITY ──► ROUTINE        │  │
│   └──────────────────────────────────────────────────────┘  │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

### 5. Dashboard (`dashboard`)

**Purpose**: Tactical operations visualization and monitoring

**Features**:
- Real-time message queue status
- Network node health overview
- Priority distribution charts
- Audit event timeline
- System metrics display

---

## Data Flow

### Normal Operation (Connected Mode)

```
1. Client submits message with JWT
        │
        ▼
2. Gateway-Core validates JWT, extracts claims
        │
        ▼
3. Gateway-Core routes to Crypto-Service for encryption
        │
        ▼
4. Encrypted message routed to destination node
        │
        ▼
5. Audit-Service logs all operations
        │
        ▼
6. Delivery acknowledgment returned to sender
```

### Degraded Operation (Disconnected Mode)

```
1. Client submits message with JWT
        │
        ▼
2. Gateway-Core validates JWT, detects destination unreachable
        │
        ▼
3. Message encrypted and queued in Store-Forward
        │
        ▼
4. Store-Forward monitors connectivity
        │
        ▼
5. On reconnection, messages dispatched by priority
        │
        ▼
6. Delivery acknowledgment returned to sender
```

---

## Security Architecture

### Zero Trust Principles

1. **Verify Explicitly**: Every service call authenticated via JWT
2. **Least Privilege**: Services have minimal required permissions
3. **Assume Breach**: All traffic encrypted, comprehensive logging

### Authentication Chain

```
┌────────────┐      ┌────────────┐      ┌────────────┐
│   Client   │─JWT─►│  Gateway   │─JWT─►│  Crypto    │
│            │      │   Core     │      │  Service   │
└────────────┘      └─────┬──────┘      └────────────┘
                          │
                          │ JWT propagated to all downstream calls
                          │
              ┌───────────┼───────────┐
              │           │           │
              ▼           ▼           ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │  Audit   │ │  Store   │ │Dashboard │
        │ Service  │ │ Forward  │ │ (R/O)    │
        └──────────┘ └──────────┘ └──────────┘
```

### Network Policies (Kubernetes)

- **Default Deny**: All ingress blocked unless explicitly allowed
- **Service Mesh**: mTLS between all pods
- **Egress Control**: Only approved external endpoints

---

## Deployment Models

### Development (Docker Compose)
- Single-node deployment
- Hot reload for development
- Local Redis instance

### Production (Kubernetes)
- Multi-replica deployments
- Redis cluster for HA
- Horizontal Pod Autoscaling
- Network policies enforced

---

## Failure Modes

| Failure | Detection | Mitigation |
|---------|-----------|------------|
| Crypto Service unavailable | Health check failure | Queue encrypted messages, retry |
| Redis unavailable | Connection timeout | In-memory fallback (limited) |
| Network partition | Heartbeat loss | Store-forward activation |
| JWT expired | 401 response | Token refresh or re-auth |
| Disk full | Metrics alert | Log rotation, queue limits |

---

## Scalability

### Horizontal Scaling
- Gateway-Core: Stateless, scale to N replicas
- Crypto-Service: Stateless, scale based on encryption load
- Audit-Service: Stateless, scale based on event volume
- Store-Forward: Stateful, Redis cluster for HA

### Performance Targets
| Metric | Target |
|--------|--------|
| FLASH message latency | < 100ms p99 |
| Messages per second | 10,000+ |
| Audit events per second | 50,000+ |
| Store-forward queue depth | 1M messages |


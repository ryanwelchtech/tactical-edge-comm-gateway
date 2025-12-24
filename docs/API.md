# API Documentation

## Overview

The Tactical Edge Communications Gateway exposes RESTful APIs for message routing, encryption, audit, and queue management. All endpoints require JWT authentication unless otherwise noted.

**📹 Demo Videos:**
- **[Dashboard Demo](../images/dashboard-demo.gif)** - Full dashboard walkthrough
- **[API Demo](../images/api-demo.gif)** - Sending messages via REST API

---

## Authentication

### Token Format

All API requests must include a valid JWT token in the Authorization header:

```
Authorization: Bearer <jwt-token>
```

### Token Generation

```bash
# Generate a token using the provided script
python scripts/generate-jwt.py --role operator --node NODE-ALPHA

# Output
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Token Claims

| Claim | Type | Description |
|-------|------|-------------|
| `sub` | string | Node identifier |
| `role` | string | User role (operator, supervisor, admin) |
| `permissions` | array | Granted permissions |
| `node_id` | string | Originating node |
| `exp` | number | Expiration timestamp |
| `iat` | number | Issued at timestamp |

---

## Gateway Core API

**Base URL**: `http://localhost:5000/api/v1`

### Send Message

**POST** `/messages`

Send a tactical message with specified precedence.

**Request Body**:
```json
{
  "precedence": "FLASH",
  "classification": "UNCLASSIFIED",
  "sender": "NODE-ALPHA",
  "recipient": "NODE-BRAVO",
  "content": "URGENT: Threat detected at grid reference 12345678",
  "ttl": 300
}
```

**Parameters**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `precedence` | string | Yes | FLASH, IMMEDIATE, PRIORITY, ROUTINE |
| `classification` | string | Yes | UNCLASSIFIED, CONFIDENTIAL, SECRET, TOP_SECRET |
| `sender` | string | Yes | Sender node identifier |
| `recipient` | string | Yes | Recipient node identifier |
| `content` | string | Yes | Message content (max 64KB) |
| `ttl` | integer | No | Time-to-live in seconds (default: 3600) |

**Response** (201 Created):
```json
{
  "message_id": "msg-550e8400-e29b-41d4-a716-446655440000",
  "status": "QUEUED",
  "precedence": "FLASH",
  "created_at": "2024-12-23T18:30:00Z",
  "estimated_delivery": "2024-12-23T18:30:00.100Z"
}
```

**Errors**:
- `400 Bad Request` - Invalid message format
- `401 Unauthorized` - Invalid or missing token
- `403 Forbidden` - Insufficient permissions
- `429 Too Many Requests` - Rate limit exceeded

---

### Get Message Status

**GET** `/messages/{message_id}`

Retrieve the status of a previously sent message.

**Response** (200 OK):
```json
{
  "message_id": "msg-550e8400-e29b-41d4-a716-446655440000",
  "status": "DELIVERED",
  "precedence": "FLASH",
  "sender": "NODE-ALPHA",
  "recipient": "NODE-BRAVO",
  "created_at": "2024-12-23T18:30:00Z",
  "delivered_at": "2024-12-23T18:30:00.085Z",
  "latency_ms": 85,
  "encrypted": true,
  "audit_trail": [
    {
      "timestamp": "2024-12-23T18:30:00.010Z",
      "event": "RECEIVED",
      "node": "GATEWAY-01"
    },
    {
      "timestamp": "2024-12-23T18:30:00.045Z",
      "event": "ENCRYPTED",
      "node": "CRYPTO-01"
    },
    {
      "timestamp": "2024-12-23T18:30:00.085Z",
      "event": "DELIVERED",
      "node": "NODE-BRAVO"
    }
  ]
}
```

**Status Values**:
| Status | Description |
|--------|-------------|
| QUEUED | Message accepted, pending processing |
| PROCESSING | Message being encrypted/routed |
| TRANSMITTED | Message sent to recipient |
| DELIVERED | Delivery confirmed by recipient |
| FAILED | Delivery failed (see error field) |
| EXPIRED | TTL exceeded before delivery |
| STORED | Queued for store-forward (disconnected) |

---

### Acknowledge Message

**POST** `/messages/{message_id}/ack`

Acknowledge receipt of a message.

**Response** (200 OK):
```json
{
  "message_id": "msg-550e8400-e29b-41d4-a716-446655440000",
  "acknowledged": true,
  "acknowledged_at": "2024-12-23T18:30:01Z",
  "acknowledged_by": "NODE-BRAVO"
}
```

---

### List Nodes

**GET** `/nodes`

List all registered tactical nodes and their status.

**Response** (200 OK):
```json
{
  "nodes": [
    {
      "node_id": "NODE-ALPHA",
      "status": "CONNECTED",
      "last_seen": "2024-12-23T18:29:55Z",
      "ip_address": "10.0.1.50",
      "capabilities": ["FLASH", "IMMEDIATE", "PRIORITY", "ROUTINE"]
    },
    {
      "node_id": "NODE-BRAVO",
      "status": "CONNECTED",
      "last_seen": "2024-12-23T18:29:58Z",
      "ip_address": "10.0.1.51",
      "capabilities": ["FLASH", "IMMEDIATE", "PRIORITY", "ROUTINE"]
    },
    {
      "node_id": "NODE-CHARLIE",
      "status": "DISCONNECTED",
      "last_seen": "2024-12-23T18:15:00Z",
      "ip_address": "10.0.1.52",
      "capabilities": ["PRIORITY", "ROUTINE"]
    }
  ],
  "total": 3,
  "connected": 2,
  "disconnected": 1
}
```

---

### System Health

**GET** `/health`

Returns service health status.

**Response** (200 OK):
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 86400,
  "checks": {
    "redis": "healthy",
    "crypto_service": "healthy",
    "audit_service": "healthy"
  }
}
```

---

## Crypto Service API

**Base URL**: `http://localhost:5001/api/v1`

### Encrypt Message

**POST** `/encrypt`

Encrypt a message payload using AES-256-GCM.

**Request Body**:
```json
{
  "plaintext": "URGENT: Threat detected at grid reference 12345678",
  "classification": "UNCLASSIFIED"
}
```

**Response** (200 OK):
```json
{
  "ciphertext": "base64-encoded-ciphertext",
  "nonce": "base64-encoded-nonce",
  "tag": "base64-encoded-tag",
  "algorithm": "AES-256-GCM",
  "version": "v1"
}
```

---

### Decrypt Message

**POST** `/decrypt`

Decrypt a previously encrypted message.

**Request Body**:
```json
{
  "ciphertext": "base64-encoded-ciphertext",
  "nonce": "base64-encoded-nonce",
  "tag": "base64-encoded-tag"
}
```

**Response** (200 OK):
```json
{
  "plaintext": "URGENT: Threat detected at grid reference 12345678",
  "verified": true
}
```

---

## Audit Service API

**Base URL**: `http://localhost:5002/api/v1`

### Query Audit Events

**GET** `/audit/events`

Query audit events with optional filters.

**Query Parameters**:
| Parameter | Type | Description |
|-----------|------|-------------|
| `control_family` | string | Filter by NIST control (AC, AU, IA, SC, SI) |
| `event_type` | string | Filter by event type |
| `node_id` | string | Filter by node |
| `start_time` | string | ISO-8601 start time |
| `end_time` | string | ISO-8601 end time |
| `limit` | integer | Max results (default: 100) |

**Response** (200 OK):
```json
{
  "events": [
    {
      "event_id": "evt-550e8400-e29b-41d4-a716-446655440000",
      "timestamp": "2024-12-23T18:30:00Z",
      "control_family": "AU",
      "event_type": "MESSAGE_SENT",
      "actor": {
        "node_id": "NODE-ALPHA",
        "role": "operator",
        "ip_address": "10.0.1.50"
      },
      "action": {
        "operation": "SEND_MESSAGE",
        "resource": "message:msg-12345",
        "outcome": "SUCCESS"
      },
      "context": {
        "precedence": "FLASH",
        "classification": "UNCLASSIFIED"
      }
    }
  ],
  "total": 1,
  "page": 1,
  "limit": 100
}
```

---

### Get Audit Statistics

**GET** `/audit/stats`

Get aggregated audit statistics.

**Response** (200 OK):
```json
{
  "period": "24h",
  "total_events": 15420,
  "by_control_family": {
    "AC": 2340,
    "AU": 8500,
    "IA": 1200,
    "SC": 2880,
    "SI": 500
  },
  "by_outcome": {
    "SUCCESS": 15100,
    "FAILURE": 320
  },
  "top_actors": [
    {"node_id": "NODE-ALPHA", "count": 5200},
    {"node_id": "NODE-BRAVO", "count": 4800}
  ]
}
```

---

## Store-Forward API

**Base URL**: `http://localhost:5003/api/v1`

### Get Queue Status

**GET** `/queue/status`

Get current queue depth and statistics.

**Response** (200 OK):
```json
{
  "queues": {
    "FLASH": {
      "depth": 0,
      "oldest_message": null
    },
    "IMMEDIATE": {
      "depth": 5,
      "oldest_message": "2024-12-23T18:25:00Z"
    },
    "PRIORITY": {
      "depth": 23,
      "oldest_message": "2024-12-23T18:00:00Z"
    },
    "ROUTINE": {
      "depth": 150,
      "oldest_message": "2024-12-23T17:00:00Z"
    }
  },
  "total_queued": 178,
  "total_expired_24h": 12
}
```

---

### Force Queue Flush

**POST** `/queue/flush`

Force immediate transmission of queued messages (Admin only).

**Response** (200 OK):
```json
{
  "flushed": 178,
  "failed": 3,
  "status": "COMPLETED"
}
```

---

## Error Responses

All error responses follow a consistent format:

```json
{
  "error": {
    "code": "INVALID_TOKEN",
    "message": "JWT token has expired",
    "details": {
      "expired_at": "2024-12-23T17:00:00Z"
    },
    "request_id": "req-550e8400-e29b-41d4-a716-446655440000"
  }
}
```

### Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| INVALID_TOKEN | 401 | JWT token invalid or expired |
| UNAUTHORIZED | 401 | Missing authentication |
| FORBIDDEN | 403 | Insufficient permissions |
| NOT_FOUND | 404 | Resource not found |
| VALIDATION_ERROR | 400 | Request validation failed |
| RATE_LIMITED | 429 | Too many requests |
| INTERNAL_ERROR | 500 | Internal server error |
| SERVICE_UNAVAILABLE | 503 | Downstream service unavailable |

---

## Rate Limits

| Endpoint | Rate Limit |
|----------|------------|
| POST /messages (FLASH) | 100/min |
| POST /messages (other) | 1000/min |
| GET endpoints | 5000/min |
| Admin endpoints | 100/min |


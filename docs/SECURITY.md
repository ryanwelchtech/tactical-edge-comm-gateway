# Security Architecture & Controls

## Overview

This document details the security architecture of the Tactical Edge Communications Gateway, including Zero Trust implementation, cryptographic controls, and NIST 800-53 compliance mapping.

---

## Zero Trust Architecture

### Core Principles Implementation

| Principle | Implementation |
|-----------|----------------|
| **Never Trust, Always Verify** | JWT validation on every request |
| **Assume Breach** | All internal traffic encrypted, comprehensive audit logging |
| **Least Privilege** | Role-based access with minimal permissions |
| **Verify Explicitly** | Service-to-service authentication required |

### Trust Boundaries

```
┌─────────────────────────────────────────────────────────────────┐
│                    EXTERNAL BOUNDARY (TLS)                       │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                SERVICE MESH BOUNDARY (mTLS)                │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │           APPLICATION BOUNDARY (JWT)                 │  │  │
│  │  │                                                      │  │  │
│  │  │   ┌─────────┐  ┌─────────┐  ┌─────────┐            │  │  │
│  │  │   │ Gateway │  │ Crypto  │  │ Audit   │            │  │  │
│  │  │   │  Core   │  │ Service │  │ Service │            │  │  │
│  │  │   └─────────┘  └─────────┘  └─────────┘            │  │  │
│  │  │                                                      │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Authentication & Authorization

### JWT Token Structure

```json
{
  "header": {
    "alg": "HS256",
    "typ": "JWT"
  },
  "payload": {
    "iss": "tacedge-gateway",
    "sub": "NODE-ALPHA",
    "aud": "tacedge-services",
    "exp": 1703376000,
    "iat": 1703372400,
    "nbf": 1703372400,
    "jti": "unique-token-id",
    "role": "operator",
    "permissions": ["message:send", "message:read", "node:status"],
    "node_id": "NODE-ALPHA",
    "classification_level": "UNCLASSIFIED"
  },
  "signature": "..."
}
```

### Role Definitions

| Role | Permissions | Use Case |
|------|-------------|----------|
| **operator** | message:send, message:read, node:status | Tactical operators |
| **supervisor** | operator + message:delete, audit:read | Shift supervisors |
| **admin** | supervisor + node:manage, config:write | System administrators |
| **service** | Inter-service calls only | Microservice accounts |

### Authentication Flow

```
┌────────┐     ┌─────────────┐     ┌─────────────┐
│ Client │────►│ JWT Verify  │────►│ Claims      │
│        │ JWT │ Signature   │     │ Extraction  │
└────────┘     └─────────────┘     └──────┬──────┘
                                          │
                                          ▼
                                   ┌─────────────┐
                                   │ RBAC Check  │
                                   │ Permission  │
                                   │ Validation  │
                                   └──────┬──────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    │                     │                     │
                    ▼                     ▼                     ▼
             ┌───────────┐         ┌───────────┐         ┌───────────┐
             │  ALLOW    │         │   DENY    │         │  AUDIT    │
             │  Request  │         │  Request  │         │   LOG     │
             └───────────┘         └───────────┘         └───────────┘
```

---

## Cryptographic Controls

### Encryption Specifications

| Component | Algorithm | Key Size | Mode |
|-----------|-----------|----------|------|
| Message Encryption | AES | 256-bit | GCM |
| Key Derivation | PBKDF2 | N/A | SHA-256, 100k iterations |
| Message Signing | HMAC | 256-bit | SHA-256 |
| Token Signing | HMAC | 256-bit | SHA-256 |
| Transport | TLS | 256-bit | 1.3 |

### Encryption Process

```python
# Key Derivation
derived_key = PBKDF2(
    password=master_key,
    salt=random_salt,
    iterations=100000,
    hash_algo=SHA256,
    key_length=32  # 256 bits
)

# Encryption
nonce = os.urandom(12)  # 96-bit nonce for GCM
cipher = AES-GCM(derived_key)
ciphertext, tag = cipher.encrypt(plaintext, nonce)

# Output
encrypted_message = {
    "ciphertext": base64(ciphertext),
    "nonce": base64(nonce),
    "tag": base64(tag),
    "salt": base64(salt),
    "version": "v1"
}
```

### Key Management

- **Master Key**: Environment variable or secrets manager
- **Rotation**: Support for key versioning and rotation
- **Derivation**: Per-message derived keys using PBKDF2
- **Storage**: Keys never persisted in logs or databases

---

## NIST 800-53 Control Mapping

### Access Control (AC)

| Control | Title | Implementation |
|---------|-------|----------------|
| AC-2 | Account Management | JWT claims define user accounts and roles |
| AC-3 | Access Enforcement | RBAC middleware validates permissions |
| AC-4 | Information Flow | Network policies restrict service communication |
| AC-6 | Least Privilege | Minimal permission sets per role |
| AC-7 | Unsuccessful Logon Attempts | Rate limiting on auth endpoints |
| AC-17 | Remote Access | TLS required for all connections |

### Audit and Accountability (AU)

| Control | Title | Implementation |
|---------|-------|----------------|
| AU-2 | Auditable Events | Defined event catalog per service |
| AU-3 | Content of Audit Records | Structured JSON with who/what/when/where |
| AU-4 | Audit Log Storage | Persistent storage with rotation |
| AU-6 | Audit Review | Dashboard visualization and export |
| AU-8 | Time Stamps | ISO-8601 UTC timestamps |
| AU-9 | Protection of Audit Info | Append-only logs, integrity verification |
| AU-12 | Audit Generation | Automatic logging at service boundaries |

### Identification and Authentication (IA)

| Control | Title | Implementation |
|---------|-------|----------------|
| IA-2 | User Identification | JWT subject claim identifies users |
| IA-4 | Identifier Management | Unique node IDs assigned |
| IA-5 | Authenticator Management | Token expiration and refresh |
| IA-8 | Non-Organizational Users | Service accounts for external integrations |

### System and Communications Protection (SC)

| Control | Title | Implementation |
|---------|-------|----------------|
| SC-8 | Transmission Confidentiality | TLS 1.3 for all connections |
| SC-12 | Cryptographic Key Management | Secure key derivation and rotation |
| SC-13 | Cryptographic Protection | AES-256-GCM encryption |
| SC-23 | Session Authenticity | JWT tokens with expiration |
| SC-28 | Protection of Information at Rest | Encrypted message storage |

### System and Information Integrity (SI)

| Control | Title | Implementation |
|---------|-------|----------------|
| SI-4 | System Monitoring | Prometheus metrics collection |
| SI-7 | Software Integrity | Container image signing |
| SI-10 | Information Input Validation | JSON schema validation |
| SI-11 | Error Handling | Sanitized error responses |

---

## Threat Model

### STRIDE Analysis

| Threat | Mitigation |
|--------|------------|
| **Spoofing** | JWT authentication, mTLS between services |
| **Tampering** | HMAC signatures, integrity verification |
| **Repudiation** | Comprehensive audit logging |
| **Information Disclosure** | AES-256 encryption, TLS transport |
| **Denial of Service** | Rate limiting, queue depth limits |
| **Elevation of Privilege** | RBAC enforcement, least privilege |

### Attack Surface

```
┌─────────────────────────────────────────────────────────────┐
│                      ATTACK SURFACE                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  EXTERNAL INTERFACES (Highest Risk)                         │
│  ├── Gateway-Core API (Port 5000)                           │
│  │   ├── Mitigation: JWT auth, rate limiting, input validation
│  │   └── Monitoring: Auth failure alerts                    │
│  └── Dashboard (Port 8080)                                  │
│      ├── Mitigation: Read-only, session management          │
│      └── Monitoring: Session anomaly detection              │
│                                                              │
│  INTERNAL INTERFACES (Medium Risk)                           │
│  ├── Inter-service APIs (Ports 5001-5003)                   │
│  │   ├── Mitigation: JWT propagation, mTLS                  │
│  │   └── Monitoring: Unusual traffic patterns               │
│  └── Redis (Port 6379)                                      │
│      ├── Mitigation: Network policy, AUTH enabled           │
│      └── Monitoring: Connection count alerts                │
│                                                              │
│  DATA STORES (Lower Risk - Internal Only)                    │
│  └── Audit Logs                                              │
│      ├── Mitigation: Append-only, integrity checks          │
│      └── Monitoring: Tamper detection                       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Security Testing

### Automated Scans
- **Container Scanning**: Trivy scans in CI/CD pipeline
- **Dependency Scanning**: pip-audit for Python packages
- **SAST**: Bandit for Python security issues
- **DAST**: OWASP ZAP for API testing

### Penetration Testing Scope
- JWT token manipulation
- Authorization bypass attempts
- Injection attacks (SQL, Command)
- Rate limit bypass
- Session hijacking

---

## Incident Response

### Security Event Categories

| Category | Examples | Response Time |
|----------|----------|---------------|
| Critical | Auth bypass, data breach | Immediate |
| High | Multiple auth failures, unusual access | < 1 hour |
| Medium | Single auth failure, config change | < 4 hours |
| Low | Informational events | Next business day |

### Alerting Thresholds

```yaml
alerts:
  - name: HighAuthFailureRate
    condition: auth_failures > 10 in 5m
    severity: high
    
  - name: UnusualPrecedencePattern
    condition: flash_messages > 100 in 1m
    severity: medium
    
  - name: AuditLogTamper
    condition: integrity_check_failed
    severity: critical
```


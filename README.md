# Tactical Edge Communications Gateway (TacEdge-Gateway)

[![CI/CD Pipeline](https://github.com/ryanwelchtech/tactical-edge-comm-gateway/actions/workflows/ci.yml/badge.svg)](https://github.com/ryanwelchtech/tactical-edge-comm-gateway/actions/workflows/ci.yml)
[![Security Scan](https://github.com/ryanwelchtech/tactical-edge-comm-gateway/actions/workflows/security-scan.yml/badge.svg)](https://github.com/ryanwelchtech/tactical-edge-comm-gateway/actions/workflows/security-scan.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A **Zero Trust**, containerized tactical communications gateway platform designed for secure message routing in defense and mission-critical environments. This system implements military-standard message precedence levels, end-to-end encryption, store-and-forward capabilities for disconnected operations, and comprehensive audit logging aligned with **NIST 800-53** control families.

![TacEdge Gateway Architecture](docs/images/architecture-diagram.png)

---

## 🎯 Mission Statement

TacEdge-Gateway simulates a tactical communications relay system designed for:
- **Contested/Degraded Environments**: Store-and-forward capability for intermittent connectivity
- **Multi-Domain Operations**: Secure message routing between tactical nodes
- **Zero Trust Security**: JWT-based authentication with service-level authorization
- **Compliance-Ready**: NIST 800-53 aligned audit logging and access controls

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TACTICAL EDGE COMM GATEWAY                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │   TACTICAL   │    │   TACTICAL   │    │   TACTICAL   │                  │
│  │   NODE A     │◄──►│   GATEWAY    │◄──►│   NODE B     │                  │
│  │  (Sender)    │    │    CORE      │    │  (Receiver)  │                  │
│  └──────────────┘    └──────┬───────┘    └──────────────┘                  │
│                             │                                               │
│         ┌───────────────────┼───────────────────┐                          │
│         │                   │                   │                          │
│         ▼                   ▼                   ▼                          │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │   CRYPTO     │    │   STORE &    │    │   AUDIT      │                  │
│  │   SERVICE    │    │   FORWARD    │    │   SERVICE    │                  │
│  │  (AES-256)   │    │   (Redis)    │    │ (NIST 800-53)│                  │
│  └──────────────┘    └──────────────┘    └──────────────┘                  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    TACTICAL OPERATIONS DASHBOARD                     │   │
│  │         Real-time message status, network health, audit logs         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Key Features

### Message Precedence Handling
Military-standard message priority levels with guaranteed delivery ordering:

| Precedence | Priority | Max Latency | Use Case |
|------------|----------|-------------|----------|
| **FLASH** | P1 | < 100ms | Immediate threat/engagement |
| **IMMEDIATE** | P2 | < 500ms | Time-critical operations |
| **PRIORITY** | P3 | < 2s | Urgent operational traffic |
| **ROUTINE** | P4 | Best effort | Administrative/logistics |

### Zero Trust Architecture
- **JWT-based Service Authentication**: All inter-service calls authenticated
- **Role-Based Access Control (RBAC)**: Operator, Supervisor, Admin roles
- **Service Mesh Ready**: mTLS between all microservices
- **No Implicit Trust**: Every request validated at service boundary

### Store-and-Forward (DNVT Mode)
- **Disconnected Operations**: Messages queued during network outages
- **Priority-Based Forwarding**: FLASH messages transmitted first on reconnection
- **Delivery Confirmation**: End-to-end acknowledgment tracking
- **TTL Management**: Configurable message expiration

### NIST 800-53 Compliance
Audit logging mapped to specific control families:

| Control Family | Implementation |
|----------------|----------------|
| **AC (Access Control)** | JWT validation, RBAC enforcement |
| **AU (Audit & Accountability)** | Structured event logging, tamper-evident logs |
| **IA (Identification & Authentication)** | Service identity verification |
| **SC (System & Communications Protection)** | AES-256-GCM encryption |
| **SI (System & Information Integrity)** | Message integrity validation |

---

## 📁 Project Structure

```
tactical-edge-comm-gateway/
├── README.md                          # Project documentation
├── LICENSE                            # MIT License
├── docker-compose.yml                 # Local development deployment
├── .github/
│   └── workflows/
│       ├── ci.yml                     # CI/CD pipeline
│       └── security-scan.yml          # Container security scanning
├── docs/
│   ├── ARCHITECTURE.md                # Detailed system architecture
│   ├── SECURITY.md                    # Security design & controls
│   ├── OPERATIONS.md                  # Operational runbook
│   └── API.md                         # API documentation
├── services/
│   ├── gateway-core/                  # Message routing & precedence
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── main.py
│   │       ├── auth.py
│   │       ├── message_handler.py
│   │       └── routes.py
│   ├── crypto-service/                # Encryption/decryption service
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── main.py
│   │       └── crypto_engine.py
│   ├── audit-service/                 # NIST 800-53 compliant logging
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── main.py
│   │       └── audit_logger.py
│   └── store-forward/                 # Disconnected ops message queue
│       ├── Dockerfile
│       ├── requirements.txt
│       └── src/
│           ├── main.py
│           └── queue_manager.py
├── dashboard/                         # Tactical operations dashboard
│   ├── Dockerfile
│   ├── package.json
│   └── src/
│       ├── index.html
│       ├── app.js
│       └── styles.css
├── deploy/
│   └── k8s/
│       └── base/                      # Kubernetes manifests
│           ├── namespace.yaml
│           ├── gateway-deployment.yaml
│           ├── crypto-deployment.yaml
│           ├── audit-deployment.yaml
│           ├── store-forward-deployment.yaml
│           ├── dashboard-deployment.yaml
│           ├── services.yaml
│           └── network-policies.yaml
├── scripts/
│   ├── demo.ps1                       # Demo script (Windows)
│   ├── demo.sh                        # Demo script (Linux/Mac)
│   └── generate-jwt.py                # JWT token generator
└── tests/
    ├── test_gateway.py
    ├── test_crypto.py
    └── test_integration.py
```

---

## 🛠️ Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+ (for local development)
- Node.js 20+ (for dashboard development)
- kubectl (for Kubernetes deployment)

### Option 1: Docker Compose (Recommended)

```bash
# Clone the repository
git clone https://github.com/ryanwelchtech/tactical-edge-comm-gateway.git
cd tactical-edge-comm-gateway

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Access the dashboard
# Open http://localhost:8080 in your browser
```

### Option 2: Local Development

```bash
# Clone the repository
git clone https://github.com/ryanwelchtech/tactical-edge-comm-gateway.git
cd tactical-edge-comm-gateway

# Start Redis (required for store-forward)
docker run -d -p 6379:6379 --name redis redis:alpine

# Install dependencies for each service
cd services/gateway-core && pip install -r requirements.txt && cd ../..
cd services/crypto-service && pip install -r requirements.txt && cd ../..
cd services/audit-service && pip install -r requirements.txt && cd ../..
cd services/store-forward && pip install -r requirements.txt && cd ../..

# Start services (each in separate terminal)
cd services/gateway-core/src && python main.py
cd services/crypto-service/src && python main.py
cd services/audit-service/src && python main.py
cd services/store-forward/src && python main.py

# Start dashboard
cd dashboard && npm install && npm start
```

### Option 3: Kubernetes Deployment

```bash
# Apply manifests
kubectl apply -f deploy/k8s/base/

# Wait for pods
kubectl wait --for=condition=ready pod -l app=tacedge -n tacedge-system --timeout=120s

# Port forward dashboard
kubectl port-forward svc/dashboard -n tacedge-system 8080:80
```

---

## 🎮 Demo Walkthrough

### 1. Generate Authentication Token

```bash
# Generate a JWT token for the Operator role
python scripts/generate-jwt.py --role operator --node NODE-ALPHA

# Output: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 2. Send a FLASH Priority Message

```bash
curl -X POST http://localhost:5000/api/v1/messages \
  -H "Authorization: Bearer <your-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "precedence": "FLASH",
    "classification": "UNCLASSIFIED",
    "sender": "NODE-ALPHA",
    "recipient": "NODE-BRAVO",
    "content": "URGENT: Threat detected at grid reference 12345678",
    "ttl": 300
  }'
```

### 3. Check Message Status

```bash
curl http://localhost:5000/api/v1/messages/<message-id>/status \
  -H "Authorization: Bearer <your-token>"
```

### 4. View Audit Logs

```bash
curl http://localhost:5002/api/v1/audit/events?control_family=AU \
  -H "Authorization: Bearer <your-token>"
```

### 5. Dashboard Access
Navigate to `http://localhost:8080` to view:
- Real-time message queue status
- Network node health
- Priority distribution charts
- Audit event timeline

---

## 🔒 Security Architecture

### Authentication Flow

```
┌────────┐     ┌─────────┐     ┌─────────────┐     ┌──────────┐
│ Client │────►│ Gateway │────►│ Crypto Svc  │────►│ Audit    │
│        │ JWT │  Core   │ JWT │             │ JWT │ Service  │
└────────┘     └─────────┘     └─────────────┘     └──────────┘
                    │
                    ▼ JWT Validation at each hop
              ┌─────────────┐
              │ Store/Fwd   │
              │ Service     │
              └─────────────┘
```

### Encryption
- **Algorithm**: AES-256-GCM
- **Key Derivation**: PBKDF2 with SHA-256
- **Message Integrity**: HMAC-SHA256 signatures
- **Transport**: TLS 1.3 (Kubernetes mTLS)

---

## 📊 Observability

### Health Endpoints
Each service exposes:
- `/health` - Liveness probe
- `/ready` - Readiness probe
- `/metrics` - Prometheus metrics

### Key Metrics
- `tacedge_messages_total{precedence, status}` - Message counts
- `tacedge_message_latency_seconds{precedence}` - Processing latency
- `tacedge_queue_depth{priority}` - Store-forward queue depth
- `tacedge_auth_failures_total{reason}` - Authentication failures

---

## 🧪 Testing

```bash
# Run unit tests
pytest tests/ -v

# Run integration tests
pytest tests/test_integration.py -v --docker

# Run security tests
pytest tests/ -v -m security
```

---

## 📜 Compliance Mapping

| NIST 800-53 Control | Implementation |
|---------------------|----------------|
| AC-2 | Account management via JWT claims |
| AC-3 | RBAC enforcement in gateway-core |
| AC-6 | Least privilege service accounts |
| AU-2 | Auditable event definitions |
| AU-3 | Audit record content (who, what, when, where) |
| AU-6 | Audit review via dashboard |
| IA-2 | Multi-factor capable (JWT + mTLS) |
| SC-8 | Transmission confidentiality (TLS + AES) |
| SC-13 | Cryptographic protection (AES-256-GCM) |
| SI-4 | System monitoring via metrics |

---

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](docs/CONTRIBUTING.md) for guidelines.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👨‍💻 Author

**Ryan Welch**  
Cloud and Systems Security Engineer | Defense & Aerospace  
[LinkedIn](https://linkedin.com/in/ryanwelch54) | [GitHub](https://github.com/ryanwelchtech)

---

## 🏷️ Keywords

`Zero Trust` `NIST 800-53` `Tactical Communications` `Defense` `Kubernetes` `Container Security` `DevSecOps` `FedRAMP` `IAMD` `C4ISR` `Microservices` `JWT` `Encryption` `Store-and-Forward`


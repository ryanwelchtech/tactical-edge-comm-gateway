# Operations Runbook

## Overview

This document provides operational guidance for deploying, monitoring, and troubleshooting the Tactical Edge Communications Gateway.

---

## Deployment

### Prerequisites Checklist

- [ ] Docker 24.0+ installed
- [ ] Docker Compose 2.0+ installed
- [ ] kubectl 1.28+ (for Kubernetes deployment)
- [ ] Minimum 4GB RAM available
- [ ] Ports 5000-5003, 6379, 8080 available

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `JWT_SECRET` | Secret for JWT signing | (none) | Yes |
| `ENCRYPTION_KEY` | Master encryption key | (none) | Yes |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379` | No |
| `LOG_LEVEL` | Logging verbosity | `INFO` | No |
| `GATEWAY_PORT` | Gateway service port | `5000` | No |
| `CRYPTO_PORT` | Crypto service port | `5001` | No |
| `AUDIT_PORT` | Audit service port | `5002` | No |
| `STORE_FWD_PORT` | Store-forward service port | `5003` | No |

### Docker Compose Deployment

```bash
# Set required environment variables
export JWT_SECRET=$(openssl rand -hex 32)
export ENCRYPTION_KEY=$(openssl rand -hex 32)

# Start all services
docker-compose up -d

# Verify all containers are running
docker-compose ps

# Expected output:
# NAME                          STATUS
# tacedge-gateway-core          Up
# tacedge-crypto-service        Up
# tacedge-audit-service         Up
# tacedge-store-forward         Up
# tacedge-dashboard             Up
# tacedge-redis                 Up
```

### Kubernetes Deployment

```bash
# Create namespace
kubectl create namespace tacedge-system

# Create secrets
kubectl create secret generic tacedge-secrets \
  --from-literal=jwt-secret=$(openssl rand -hex 32) \
  --from-literal=encryption-key=$(openssl rand -hex 32) \
  -n tacedge-system

# Apply manifests
kubectl apply -f deploy/k8s/base/

# Wait for pods
kubectl wait --for=condition=ready pod -l app=tacedge \
  -n tacedge-system --timeout=120s

# Verify deployment
kubectl get pods -n tacedge-system
```

---

## Health Checks

### Service Health Endpoints

| Service | Health Endpoint | Ready Endpoint |
|---------|-----------------|----------------|
| Gateway Core | `http://localhost:5000/health` | `http://localhost:5000/ready` |
| Crypto Service | `http://localhost:5001/health` | `http://localhost:5001/ready` |
| Audit Service | `http://localhost:5002/health` | `http://localhost:5002/ready` |
| Store-Forward | `http://localhost:5003/health` | `http://localhost:5003/ready` |
| Dashboard | `http://localhost:8080/health` | `http://localhost:8080/ready` |

### Health Check Script

```bash
#!/bin/bash
# health-check.sh

SERVICES=("gateway-core:5000" "crypto-service:5001" "audit-service:5002" "store-forward:5003")

for service in "${SERVICES[@]}"; do
  name="${service%%:*}"
  port="${service##*:}"
  
  response=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${port}/health")
  
  if [ "$response" = "200" ]; then
    echo "✅ ${name}: HEALTHY"
  else
    echo "❌ ${name}: UNHEALTHY (HTTP ${response})"
  fi
done
```

---

## Monitoring

### Key Metrics

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `tacedge_messages_total` | Total messages processed | N/A (counter) |
| `tacedge_message_latency_seconds` | Message processing time | > 200ms (FLASH) |
| `tacedge_queue_depth` | Store-forward queue size | > 10,000 |
| `tacedge_auth_failures_total` | Authentication failures | > 10/min |
| `tacedge_encryption_errors_total` | Encryption failures | > 0 |

### Prometheus Scrape Config

```yaml
scrape_configs:
  - job_name: 'tacedge'
    static_configs:
      - targets:
        - 'gateway-core:5000'
        - 'crypto-service:5001'
        - 'audit-service:5002'
        - 'store-forward:5003'
    metrics_path: /metrics
    scrape_interval: 15s
```

### Grafana Dashboard Panels

1. **Message Throughput** - Messages/second by precedence
2. **Latency Distribution** - p50, p95, p99 by precedence
3. **Queue Depth** - Store-forward queue size over time
4. **Error Rate** - Auth failures, encryption errors
5. **Node Status** - Connected/disconnected nodes

---

## Troubleshooting

### Common Issues

#### Issue: JWT Validation Failing

**Symptoms**: 401 Unauthorized responses

**Diagnostic Steps**:
```bash
# Check JWT_SECRET is set
docker-compose exec gateway-core printenv JWT_SECRET

# Verify token format
python scripts/generate-jwt.py --role operator --node TEST --debug

# Check service logs
docker-compose logs gateway-core | grep -i auth
```

**Resolution**:
1. Ensure JWT_SECRET matches across all services
2. Verify token is not expired
3. Check token format (Bearer prefix)

---

#### Issue: Store-Forward Queue Growing

**Symptoms**: Queue depth increasing, messages not delivering

**Diagnostic Steps**:
```bash
# Check Redis connectivity
docker-compose exec store-forward redis-cli -h redis ping

# Check queue depth
docker-compose exec store-forward redis-cli -h redis llen tacedge:queue:flash

# Check destination node status
curl http://localhost:5000/api/v1/nodes
```

**Resolution**:
1. Verify destination node is reachable
2. Check network policies/firewall
3. Increase retry attempts if transient failures

---

#### Issue: High Message Latency

**Symptoms**: FLASH messages exceeding 100ms SLA

**Diagnostic Steps**:
```bash
# Check service resource usage
docker stats

# Check encryption service load
curl http://localhost:5001/metrics | grep latency

# Profile gateway processing
docker-compose logs gateway-core | grep "processing_time"
```

**Resolution**:
1. Scale crypto-service replicas
2. Increase resource limits
3. Check for memory pressure

---

#### Issue: Audit Logs Not Appearing

**Symptoms**: Events not visible in dashboard or API

**Diagnostic Steps**:
```bash
# Check audit service health
curl http://localhost:5002/health

# Check event count
curl http://localhost:5002/api/v1/audit/stats

# Verify JWT propagation
docker-compose logs audit-service | grep "Received event"
```

**Resolution**:
1. Verify JWT propagation to audit service
2. Check disk space for log storage
3. Verify event schema matches expected format

---

## Maintenance Procedures

### Log Rotation

```bash
# Configure log rotation in docker-compose.yml
services:
  gateway-core:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "5"
```

### Secret Rotation

```bash
# Generate new secrets
NEW_JWT_SECRET=$(openssl rand -hex 32)
NEW_ENCRYPTION_KEY=$(openssl rand -hex 32)

# Update Kubernetes secret
kubectl create secret generic tacedge-secrets \
  --from-literal=jwt-secret=$NEW_JWT_SECRET \
  --from-literal=encryption-key=$NEW_ENCRYPTION_KEY \
  -n tacedge-system --dry-run=client -o yaml | kubectl apply -f -

# Rolling restart services
kubectl rollout restart deployment -l app=tacedge -n tacedge-system
```

### Backup Procedures

```bash
# Backup audit logs
docker-compose exec audit-service tar -czf /backup/audit-$(date +%Y%m%d).tar.gz /data/audit

# Backup Redis data
docker-compose exec redis redis-cli BGSAVE
docker cp tacedge-redis:/data/dump.rdb ./backup/redis-$(date +%Y%m%d).rdb
```

---

## Disaster Recovery

### Service Recovery Order

1. **Redis** - Required for store-forward
2. **Crypto Service** - Required for encryption
3. **Audit Service** - Required for compliance
4. **Gateway Core** - Main entry point
5. **Store-Forward** - Queue processing
6. **Dashboard** - Monitoring

### Recovery Commands

```bash
# Full system restart
docker-compose down
docker-compose up -d

# Single service restart
docker-compose restart gateway-core

# Force recreate containers
docker-compose up -d --force-recreate
```

### Data Recovery

```bash
# Restore Redis backup
docker cp ./backup/redis-20241223.rdb tacedge-redis:/data/dump.rdb
docker-compose restart redis

# Restore audit logs
docker cp ./backup/audit-20241223.tar.gz tacedge-audit-service:/restore/
docker-compose exec audit-service tar -xzf /restore/audit-20241223.tar.gz -C /
```

---

## Performance Tuning

### Resource Recommendations

| Service | CPU Request | CPU Limit | Memory Request | Memory Limit |
|---------|-------------|-----------|----------------|--------------|
| Gateway Core | 250m | 1000m | 256Mi | 512Mi |
| Crypto Service | 500m | 2000m | 256Mi | 512Mi |
| Audit Service | 100m | 500m | 128Mi | 256Mi |
| Store-Forward | 250m | 1000m | 256Mi | 512Mi |
| Dashboard | 50m | 200m | 64Mi | 128Mi |

### Scaling Guidelines

```bash
# Scale crypto service for high encryption load
kubectl scale deployment crypto-service --replicas=3 -n tacedge-system

# Scale gateway for high message volume
kubectl scale deployment gateway-core --replicas=5 -n tacedge-system
```


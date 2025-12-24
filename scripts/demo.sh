#!/bin/bash
# TacEdge Gateway Demo Script (Linux/Mac)
# Demonstrates key functionality of the tactical communications platform

set -e

echo ""
echo "============================================"
echo "  TacEdge Gateway - Demonstration Script   "
echo "============================================"
echo ""

# Configuration
GATEWAY_URL="http://localhost:5000"
CRYPTO_URL="http://localhost:5001"
AUDIT_URL="http://localhost:5002"
STORE_FWD_URL="http://localhost:5003"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Check if services are running
echo -e "${YELLOW}[1/6] Checking service health...${NC}"

check_health() {
    local name=$1
    local url=$2
    
    if curl -s "$url" > /dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} $name: HEALTHY"
        return 0
    else
        echo -e "  ${RED}✗${NC} $name: UNAVAILABLE"
        return 1
    fi
}

check_health "Gateway Core" "$GATEWAY_URL/health" || true
check_health "Crypto Service" "$CRYPTO_URL/health" || true
check_health "Audit Service" "$AUDIT_URL/health" || true
check_health "Store-Forward" "$STORE_FWD_URL/health" || true

echo ""

# Generate JWT token
echo -e "${YELLOW}[2/6] Generating authentication token...${NC}"

TOKEN=$(python3 scripts/generate-jwt.py --node NODE-DEMO --role operator 2>/dev/null | grep "^eyJ" | head -1) || \
TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJOT0RFLU1PQ0siLCJyb2xlIjoib3BlcmF0b3IifQ.demo"

echo "  Token generated: ${TOKEN:0:50}..."
echo ""

# Send test messages
echo -e "${YELLOW}[3/6] Sending test messages...${NC}"

for precedence in FLASH IMMEDIATE PRIORITY ROUTINE; do
    response=$(curl -s -X POST "$GATEWAY_URL/api/v1/messages" \
        -H "Authorization: Bearer $TOKEN" \
        -H "Content-Type: application/json" \
        -d "{
            \"precedence\": \"$precedence\",
            \"classification\": \"UNCLASSIFIED\",
            \"sender\": \"NODE-DEMO\",
            \"recipient\": \"NODE-BRAVO\",
            \"content\": \"Test message with $precedence precedence - $(date +%H:%M:%S)\",
            \"ttl\": 3600
        }" 2>/dev/null) || response=""
    
    if [ -n "$response" ]; then
        msg_id=$(echo "$response" | grep -o '"message_id":"[^"]*"' | cut -d'"' -f4)
        echo -e "  ${GREEN}✓${NC} $precedence message sent: $msg_id"
    else
        echo -e "  ${RED}✗${NC} $precedence message failed"
    fi
done

echo ""

# Check queue status
echo -e "${YELLOW}[4/6] Checking queue status...${NC}"

queue_status=$(curl -s "$STORE_FWD_URL/api/v1/queue/status" 2>/dev/null) || queue_status=""

if [ -n "$queue_status" ]; then
    echo "  Queue Status:"
    echo "$queue_status" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"    FLASH:     {data['queues'].get('FLASH', {}).get('depth', 0)} messages\")
print(f\"    IMMEDIATE: {data['queues'].get('IMMEDIATE', {}).get('depth', 0)} messages\")
print(f\"    PRIORITY:  {data['queues'].get('PRIORITY', {}).get('depth', 0)} messages\")
print(f\"    ROUTINE:   {data['queues'].get('ROUTINE', {}).get('depth', 0)} messages\")
print(f\"    Total:     {data.get('total_queued', 0)} messages\")
" 2>/dev/null || echo "  Could not parse queue status"
else
    echo "  Could not retrieve queue status"
fi

echo ""

# List nodes
echo -e "${YELLOW}[5/6] Listing registered nodes...${NC}"

nodes=$(curl -s -H "Authorization: Bearer $TOKEN" "$GATEWAY_URL/api/v1/nodes" 2>/dev/null) || nodes=""

if [ -n "$nodes" ]; then
    echo "$nodes" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for node in data.get('nodes', []):
    status = node.get('status', 'UNKNOWN')
    color = '\033[0;32m' if status == 'CONNECTED' else '\033[0;31m'
    reset = '\033[0m'
    print(f\"  {node.get('node_id', 'UNKNOWN')}: {color}{status}{reset}\")
print(f\"  Total: {data.get('connected', 0)} connected, {data.get('disconnected', 0)} disconnected\")
" 2>/dev/null || echo "  Could not parse nodes"
else
    echo "  Could not retrieve nodes"
fi

echo ""

# Check audit events
echo -e "${YELLOW}[6/6] Recent audit events...${NC}"

events=$(curl -s -H "Authorization: Bearer $TOKEN" "$AUDIT_URL/api/v1/audit/events?limit=5" 2>/dev/null) || events=""

if [ -n "$events" ]; then
    echo "$events" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for event in data.get('events', [])[:5]:
    cf = event.get('control_family', '??')
    et = event.get('event_type', 'UNKNOWN')
    ts = event.get('timestamp', '')[:19]
    print(f\"  [{cf}] {et} - {ts}\")
" 2>/dev/null || echo "  Could not parse events"
else
    echo "  Could not retrieve audit events"
fi

echo ""
echo -e "${CYAN}============================================${NC}"
echo -e "${CYAN}  Demo complete! Dashboard: http://localhost:8080${NC}"
echo -e "${CYAN}============================================${NC}"
echo ""


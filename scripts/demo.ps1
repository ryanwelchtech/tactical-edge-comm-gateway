# TacEdge Gateway Demo Script (Windows PowerShell)
# Demonstrates key functionality of the tactical communications platform

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  TacEdge Gateway - Demonstration Script   " -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$GATEWAY_URL = "http://localhost:5000"
$CRYPTO_URL = "http://localhost:5001"
$AUDIT_URL = "http://localhost:5002"
$STORE_FWD_URL = "http://localhost:5003"

# Check if services are running
Write-Host "[1/6] Checking service health..." -ForegroundColor Yellow

$services = @(
    @{Name="Gateway Core"; URL="$GATEWAY_URL/health"},
    @{Name="Crypto Service"; URL="$CRYPTO_URL/health"},
    @{Name="Audit Service"; URL="$AUDIT_URL/health"},
    @{Name="Store-Forward"; URL="$STORE_FWD_URL/health"}
)

foreach ($service in $services) {
    try {
        $response = Invoke-RestMethod -Uri $service.URL -Method Get -ErrorAction Stop
        Write-Host "  ✓ $($service.Name): HEALTHY" -ForegroundColor Green
    } catch {
        Write-Host "  ✗ $($service.Name): UNAVAILABLE" -ForegroundColor Red
    }
}

Write-Host ""

# Generate JWT token
Write-Host "[2/6] Generating authentication token..." -ForegroundColor Yellow

try {
    $token = python scripts/generate-jwt.py --node NODE-DEMO --role operator 2>&1 | Select-String -Pattern "^eyJ" | ForEach-Object { $_.Line }
    if (-not $token) {
        # Fallback demo token
        $token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJOT0RFLU1PQ0siLCJyb2xlIjoib3BlcmF0b3IifQ.demo"
    }
    Write-Host "  Token generated: $($token.Substring(0, 50))..." -ForegroundColor Gray
} catch {
    Write-Host "  Using demo token" -ForegroundColor Gray
    $token = "demo-token"
}

Write-Host ""

# Send test messages
Write-Host "[3/6] Sending test messages..." -ForegroundColor Yellow

$precedences = @("FLASH", "IMMEDIATE", "PRIORITY", "ROUTINE")

foreach ($precedence in $precedences) {
    $body = @{
        precedence = $precedence
        classification = "UNCLASSIFIED"
        sender = "NODE-DEMO"
        recipient = "NODE-BRAVO"
        content = "Test message with $precedence precedence - $(Get-Date -Format 'HH:mm:ss')"
        ttl = 3600
    } | ConvertTo-Json
    
    try {
        $headers = @{
            "Authorization" = "Bearer $token"
            "Content-Type" = "application/json"
        }
        
        $response = Invoke-RestMethod -Uri "$GATEWAY_URL/api/v1/messages" `
            -Method Post -Body $body -Headers $headers -ErrorAction Stop
        
        Write-Host "  ✓ $precedence message sent: $($response.message_id)" -ForegroundColor Green
    } catch {
        Write-Host "  ✗ $precedence message failed: $_" -ForegroundColor Red
    }
}

Write-Host ""

# Check queue status
Write-Host "[4/6] Checking queue status..." -ForegroundColor Yellow

try {
    $response = Invoke-RestMethod -Uri "$STORE_FWD_URL/api/v1/queue/status" -Method Get -ErrorAction Stop
    Write-Host "  Queue Status:" -ForegroundColor Gray
    Write-Host "    FLASH:     $($response.queues.FLASH.depth) messages" -ForegroundColor Magenta
    Write-Host "    IMMEDIATE: $($response.queues.IMMEDIATE.depth) messages" -ForegroundColor Yellow
    Write-Host "    PRIORITY:  $($response.queues.PRIORITY.depth) messages" -ForegroundColor Green
    Write-Host "    ROUTINE:   $($response.queues.ROUTINE.depth) messages" -ForegroundColor Blue
    Write-Host "    Total:     $($response.total_queued) messages" -ForegroundColor White
} catch {
    Write-Host "  Could not retrieve queue status" -ForegroundColor Red
}

Write-Host ""

# List nodes
Write-Host "[5/6] Listing registered nodes..." -ForegroundColor Yellow

try {
    $headers = @{ "Authorization" = "Bearer $token" }
    $response = Invoke-RestMethod -Uri "$GATEWAY_URL/api/v1/nodes" -Method Get -Headers $headers -ErrorAction Stop
    
    foreach ($node in $response.nodes) {
        $statusColor = if ($node.status -eq "CONNECTED") { "Green" } else { "Red" }
        Write-Host "  $($node.node_id): $($node.status)" -ForegroundColor $statusColor
    }
    Write-Host "  Total: $($response.connected) connected, $($response.disconnected) disconnected" -ForegroundColor Gray
} catch {
    Write-Host "  Could not retrieve nodes" -ForegroundColor Red
}

Write-Host ""

# Check audit events
Write-Host "[6/6] Recent audit events..." -ForegroundColor Yellow

try {
    $headers = @{ "Authorization" = "Bearer $token" }
    $response = Invoke-RestMethod -Uri "$AUDIT_URL/api/v1/audit/events?limit=5" -Method Get -Headers $headers -ErrorAction Stop
    
    foreach ($event in $response.events) {
        Write-Host "  [$($event.control_family)] $($event.event_type) - $($event.timestamp)" -ForegroundColor Gray
    }
} catch {
    Write-Host "  Could not retrieve audit events" -ForegroundColor Red
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Demo complete! Dashboard: http://localhost:8080" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""


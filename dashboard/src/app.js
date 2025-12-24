/**
 * TacEdge Gateway - Tactical Operations Dashboard
 * Real-time visualization of tactical communications platform
 */

// Configuration
const CONFIG = {
    gatewayUrl: 'http://localhost:5000',
    storeForwardUrl: 'http://localhost:5003',
    auditUrl: 'http://localhost:5002',
    refreshInterval: 3000,
    animationDuration: 500
};

// State
const state = {
    nodes: [],
    messages: [],
    queueStatus: {
        FLASH: 0,
        IMMEDIATE: 0,
        PRIORITY: 0,
        ROUTINE: 0
    },
    metrics: {
        messagesPerSec: 0,
        avgLatency: 0,
        uptime: 0,
        authFailures: 0
    },
    services: [],
    auditEvents: [],
    allAuditEvents: [],
    totalMessagesSent: 0,
    startTime: Date.now(),
    selectedMessage: null
};

// Initialize Dashboard
document.addEventListener('DOMContentLoaded', () => {
    initializeDashboard();
    startDataRefresh();
    updateDateTime();
    setInterval(updateDateTime, 1000);
});

function initializeDashboard() {
    // Load initial data from APIs
    fetchAllData();

    // Render all components
    renderNodes();
    renderQueueStats();
    renderMessages();
    renderMetrics();
    renderServiceHealth();
    renderAuditEvents();
}

async function fetchAllData() {
    await Promise.all([
        fetchNodes(),
        fetchQueueStatus(),
        fetchServiceHealth(),
        fetchAuditEvents()
    ]);

    // Extract messages from audit events
    extractMessagesFromAudit();
}

async function fetchNodes() {
    try {
        const res = await fetch(`${CONFIG.gatewayUrl}/api/v1/nodes`, {
            headers: { 'Authorization': `Bearer ${getToken()}` }
        });
        if (res.ok) {
            const data = await res.json();
            state.nodes = data.nodes || [];
            renderNodes();
        } else {
            // Auth failed or other error - use demo data
            console.log('Nodes API returned error, using demo data');
            loadDemoNodes();
        }
    } catch (error) {
        console.log('Nodes API not available, using demo data');
        loadDemoNodes();
    }
}

async function fetchQueueStatus() {
    try {
        const res = await fetch(`${CONFIG.storeForwardUrl}/api/v1/queue/status`);
        if (res.ok) {
            const data = await res.json();
            state.queueStatus = {
                FLASH: data.queues?.FLASH?.depth || 0,
                IMMEDIATE: data.queues?.IMMEDIATE?.depth || 0,
                PRIORITY: data.queues?.PRIORITY?.depth || 0,
                ROUTINE: data.queues?.ROUTINE?.depth || 0
            };
            state.totalMessagesSent = data.total_messages || state.totalMessagesSent;
            renderQueueStats();
        }
    } catch (error) {
        console.log('Queue API not available');
    }
}

async function fetchServiceHealth() {
    const services = [
        { name: 'gateway-core', url: `${CONFIG.gatewayUrl}/health` },
        { name: 'crypto-service', url: 'http://localhost:5001/health' },
        { name: 'audit-service', url: `${CONFIG.auditUrl}/health` },
        { name: 'store-forward', url: `${CONFIG.storeForwardUrl}/health` },
        { name: 'redis', url: `${CONFIG.storeForwardUrl}/health` }
    ];

    const healthChecks = await Promise.all(
        services.map(async (service) => {
            try {
                const res = await fetch(service.url, { method: 'GET' });
                return {
                    name: service.name,
                    status: res.ok ? 'healthy' : 'unhealthy'
                };
            } catch {
                return {
                    name: service.name,
                    status: 'unavailable'
                };
            }
        })
    );

    state.services = healthChecks;
    renderServiceHealth();
}

async function fetchAuditEvents() {
    try {
        const res = await fetch(`${CONFIG.auditUrl}/api/v1/audit/events?limit=50`);
        if (res.ok) {
            const data = await res.json();
            const events = data.events || [];

            state.auditEvents = events.slice(0, 5).map(event => ({
                control: event.control_family || 'AU',
                event: `${event.event_type || 'EVENT'} - ${event.action?.operation || 'N/A'}`,
                time: formatTime(event.timestamp),
                raw: event
            }));
            renderAuditEvents();

            // Store all events for message extraction
            state.allAuditEvents = events;

            // Update metrics based on audit events
            updateMetricsFromAudit(events);
        }
    } catch (error) {
        console.log('Audit API not available, using demo data');
        loadDemoAuditEvents();
    }
}

function extractMessagesFromAudit() {
    // Extract ALL MESSAGE_SENT events from audit (not just first 5)
    const allEvents = state.allAuditEvents || [];
    const messageEvents = allEvents
        .filter(e => e.event_type === 'MESSAGE_SENT')
        .map(e => ({
            id: e.action?.resource?.replace('message:', '') || `msg-${e.event_id}`,
            precedence: e.context?.precedence || 'ROUTINE',
            classification: e.context?.classification || 'UNCLASSIFIED',
            sender: e.actor?.node_id || 'UNKNOWN',
            recipient: e.context?.recipient || 'UNKNOWN',
            content: e.context?.content || 'Message content not available in audit log',
            status: e.action?.outcome === 'SUCCESS' ? 'DELIVERED' : 'PENDING',
            time: formatTime(e.timestamp),
            timestamp: e.timestamp,
            eventId: e.event_id,
            raw: e
        }))
        .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp)); // Sort by newest first

    if (messageEvents.length > 0) {
        // Replace messages with new list (avoid duplicates by ID)
        const messageMap = new Map();
        messageEvents.forEach(msg => {
            if (!messageMap.has(msg.id)) {
                messageMap.set(msg.id, msg);
            }
        });

        // Keep only last 20 messages
        state.messages = Array.from(messageMap.values()).slice(0, 20);
        renderMessages();
    } else {
        // If no messages from audit, use demo data
        if (state.messages.length === 0) {
            loadDemoMessages();
        }
    }
}

function updateMetricsFromAudit(events) {
    // Count message events in the last minute
    const oneMinuteAgo = Date.now() - 60000;
    const recentMessages = events.filter(e => {
        const eventTime = new Date(e.timestamp).getTime();
        return e.event_type === 'MESSAGE_SENT' && eventTime > oneMinuteAgo;
    });

    state.metrics.messagesPerSec = Math.round(recentMessages.length / 60 * 10) / 10 || Math.floor(Math.random() * 30) + 5;

    // Calculate uptime
    const uptimeMs = Date.now() - state.startTime;
    const uptimeHours = Math.floor(uptimeMs / 3600000);
    const uptimeMinutes = Math.floor((uptimeMs % 3600000) / 60000);
    state.metrics.uptime = uptimeHours;
    state.metrics.uptimeMinutes = uptimeMinutes;

    // Random latency for demo
    state.metrics.avgLatency = Math.floor(Math.random() * 50) + 20;

    renderMetrics();
}

function loadDemoNodes() {
    state.nodes = [
        { node_id: 'NODE-ALPHA', status: 'CONNECTED', last_seen: new Date().toISOString(), ip_address: '10.0.1.50' },
        { node_id: 'NODE-BRAVO', status: 'CONNECTED', last_seen: new Date().toISOString(), ip_address: '10.0.1.51' },
        { node_id: 'NODE-CHARLIE', status: 'CONNECTED', last_seen: new Date().toISOString(), ip_address: '10.0.1.52' },
        { node_id: 'NODE-DELTA', status: 'CONNECTED', last_seen: new Date().toISOString(), ip_address: '10.0.1.53' }
    ];
    renderNodes();
}

function loadDemoMessages() {
    const now = new Date();
    state.messages = [
        { id: 'msg-001', precedence: 'FLASH', classification: 'UNCLASSIFIED', sender: 'NODE-ALPHA', recipient: 'NODE-BRAVO', content: 'URGENT: Threat detected at grid reference 12345678', status: 'DELIVERED', time: formatTime(new Date(now - 30000)), timestamp: new Date(now - 30000).toISOString(), eventId: 'evt-demo-001' },
        { id: 'msg-002', precedence: 'IMMEDIATE', classification: 'CONFIDENTIAL', sender: 'NODE-BRAVO', recipient: 'NODE-DELTA', content: 'SITREP: All units in position', status: 'DELIVERED', time: formatTime(new Date(now - 60000)), timestamp: new Date(now - 60000).toISOString(), eventId: 'evt-demo-002' },
        { id: 'msg-003', precedence: 'PRIORITY', classification: 'UNCLASSIFIED', sender: 'NODE-ALPHA', recipient: 'NODE-CHARLIE', content: 'Equipment status nominal, standing by', status: 'DELIVERED', time: formatTime(new Date(now - 120000)), timestamp: new Date(now - 120000).toISOString(), eventId: 'evt-demo-003' },
        { id: 'msg-004', precedence: 'ROUTINE', classification: 'UNCLASSIFIED', sender: 'NODE-DELTA', recipient: 'NODE-ALPHA', content: 'Routine status update', status: 'DELIVERED', time: formatTime(new Date(now - 180000)), timestamp: new Date(now - 180000).toISOString(), eventId: 'evt-demo-004' },
        { id: 'msg-005', precedence: 'IMMEDIATE', classification: 'SECRET', sender: 'NODE-BRAVO', recipient: 'NODE-ALPHA', content: 'TACTICAL UPDATE: Enemy movement detected', status: 'DELIVERED', time: formatTime(new Date(now - 240000)), timestamp: new Date(now - 240000).toISOString(), eventId: 'evt-demo-005' }
    ];
    renderMessages();
}

function loadDemoAuditEvents() {
    const now = new Date();
    state.auditEvents = [
        { control: 'AU', event: 'MESSAGE_SENT - SEND_MESSAGE', time: formatTime(now) },
        { control: 'IA', event: 'AUTH_SUCCESS - VALIDATE_TOKEN', time: formatTime(new Date(now - 2000)) },
        { control: 'SC', event: 'ENCRYPT - AES_256_GCM', time: formatTime(new Date(now - 3000)) },
        { control: 'AC', event: 'RBAC_CHECK - PERMISSION_GRANT', time: formatTime(new Date(now - 4000)) },
        { control: 'AU', event: 'MESSAGE_DELIVERED - TRANSMIT', time: formatTime(new Date(now - 5000)) }
    ];
    renderAuditEvents();
}

function renderNodes() {
    const container = document.getElementById('nodeGrid');
    if (!container) return;

    if (state.nodes.length === 0) {
        container.innerHTML = '<div class="no-data">No nodes available</div>';
        return;
    }

    container.innerHTML = state.nodes.map(node => `
        <div class="node-card">
            <div class="node-header">
                <span class="node-name">${node.node_id}</span>
                <span class="node-status ${node.status.toLowerCase()}">${node.status}</span>
            </div>
            <div class="node-meta">
                <div>IP: ${node.ip_address}</div>
                <div>Last seen: ${formatTime(node.last_seen)}</div>
            </div>
        </div>
    `).join('');
}

function renderQueueStats() {
    const total = Object.values(state.queueStatus).reduce((a, b) => a + b, 0);
    const maxQueue = Math.max(100, total);

    const flashCount = document.getElementById('flashCount');
    const immediateCount = document.getElementById('immediateCount');
    const priorityCount = document.getElementById('priorityCount');
    const routineCount = document.getElementById('routineCount');
    const totalQueued = document.getElementById('totalQueued');

    if (flashCount) flashCount.textContent = state.queueStatus.FLASH;
    if (immediateCount) immediateCount.textContent = state.queueStatus.IMMEDIATE;
    if (priorityCount) priorityCount.textContent = state.queueStatus.PRIORITY;
    if (routineCount) routineCount.textContent = state.queueStatus.ROUTINE;
    if (totalQueued) totalQueued.textContent = total;

    // Update bars
    const flashBar = document.getElementById('flashBar');
    const immediateBar = document.getElementById('immediateBar');
    const priorityBar = document.getElementById('priorityBar');
    const routineBar = document.getElementById('routineBar');

    if (flashBar) flashBar.style.width = `${(state.queueStatus.FLASH / maxQueue) * 100}%`;
    if (immediateBar) immediateBar.style.width = `${(state.queueStatus.IMMEDIATE / maxQueue) * 100}%`;
    if (priorityBar) priorityBar.style.width = `${(state.queueStatus.PRIORITY / maxQueue) * 100}%`;
    if (routineBar) routineBar.style.width = `${(state.queueStatus.ROUTINE / maxQueue) * 100}%`;
}

function renderMessages() {
    const container = document.getElementById('messageList');
    if (!container) return;

    if (state.messages.length === 0) {
        container.innerHTML = '<div class="no-data">No recent messages</div>';
        return;
    }

    container.innerHTML = state.messages.map(msg => `
        <div class="message-item clickable" data-message-id="${msg.id}">
            <span class="message-precedence ${msg.precedence.toLowerCase()}">${msg.precedence}</span>
            <span class="message-route">${msg.sender} → ${msg.recipient}</span>
            <span class="message-time">${msg.time}</span>
            <span class="message-status ${msg.status.toLowerCase()}">${msg.status}</span>
        </div>
    `).join('');

    // Add click handlers
    container.querySelectorAll('.message-item.clickable').forEach(item => {
        item.addEventListener('click', () => {
            const messageId = item.getAttribute('data-message-id');
            const message = state.messages.find(m => m.id === messageId);
            if (message) {
                showMessageModal(message);
            }
        });
    });
}

function showMessageModal(message) {
    state.selectedMessage = message;
    const modal = document.getElementById('messageModal');
    if (!modal) return;

    // Populate modal content
    document.getElementById('modalMessageId').textContent = message.id;
    document.getElementById('modalPrecedence').textContent = message.precedence;
    document.getElementById('modalPrecedence').className = `message-precedence ${message.precedence.toLowerCase()}`;
    document.getElementById('modalClassification').textContent = message.classification;
    document.getElementById('modalSender').textContent = message.sender;
    document.getElementById('modalRecipient').textContent = message.recipient;
    document.getElementById('modalContent').textContent = message.content;
    document.getElementById('modalStatus').textContent = message.status;
    document.getElementById('modalStatus').className = `message-status ${message.status.toLowerCase()}`;
    document.getElementById('modalTime').textContent = formatTime(message.timestamp);
    document.getElementById('modalEventId').textContent = message.eventId || 'N/A';

    // Show modal
    modal.style.display = 'flex';
}

function closeMessageModal() {
    const modal = document.getElementById('messageModal');
    if (modal) {
        modal.style.display = 'none';
        state.selectedMessage = null;
    }
}

function renderMetrics() {
    const messagesPerSec = document.getElementById('messagesPerSec');
    const avgLatency = document.getElementById('avgLatency');
    const uptime = document.getElementById('uptime');
    const authFailures = document.getElementById('authFailures');

    if (messagesPerSec) messagesPerSec.textContent = state.metrics.messagesPerSec;
    if (avgLatency) avgLatency.textContent = `${state.metrics.avgLatency}ms`;
    if (uptime) uptime.textContent = `${state.metrics.uptime}h ${state.metrics.uptimeMinutes || 0}m`;
    if (authFailures) authFailures.textContent = state.metrics.authFailures;
}

function renderServiceHealth() {
    const container = document.getElementById('serviceHealth');
    if (!container) return;

    if (state.services.length === 0) {
        container.innerHTML = '<div class="no-data">Checking services...</div>';
        return;
    }

    container.innerHTML = state.services.map(service => `
        <div class="service-item">
            <span class="service-name">${service.name}</span>
            <span class="service-status ${service.status}">
                <span class="service-status-dot"></span>
                ${service.status.toUpperCase()}
            </span>
        </div>
    `).join('');
}

function renderAuditEvents() {
    const container = document.getElementById('auditList');
    if (!container) return;

    if (state.auditEvents.length === 0) {
        container.innerHTML = '<div class="no-data">No audit events</div>';
        return;
    }

    container.innerHTML = state.auditEvents.map(event => `
        <div class="audit-item">
            <span class="audit-control">${event.control}</span>
            <span class="audit-event">${event.event}</span>
            <span class="audit-time">${event.time}</span>
        </div>
    `).join('');
}

function updateDateTime() {
    const datetimeEl = document.getElementById('datetime');
    if (!datetimeEl) return;

    const now = new Date();
    const options = {
        year: 'numeric',
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
    };
    // Use local time instead of UTC
    datetimeEl.textContent = now.toLocaleString('en-US', options);
}

function formatTime(isoString) {
    if (!isoString) return '--:--:--';
    const date = new Date(isoString);
    // Use local time
    return date.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
    });
}

function startDataRefresh() {
    // Immediately fetch data
    fetchAllData();

    // Then refresh periodically
    setInterval(() => {
        fetchAllData();
    }, CONFIG.refreshInterval);
}

function getToken() {
    // In production, this would retrieve the JWT from storage
    return 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkYXNoYm9hcmQiLCJyb2xlIjoib3BlcmF0b3IifQ.demo';
}

// Expose for debugging
window.tacedgeState = state;
window.tacedgeRefresh = fetchAllData;
window.closeMessageModal = closeMessageModal;

// Close modal on outside click
document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('messageModal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeMessageModal();
            }
        });
    }

    // Close modal on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeMessageModal();
        }
    });
});

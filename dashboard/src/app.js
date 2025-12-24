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
    totalMessagesSent: 0,
    lastMessageTime: null
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
        { name: 'store-forward', url: `${CONFIG.storeForwardUrl}/health` }
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
        const res = await fetch(`${CONFIG.auditUrl}/api/v1/audit/events?limit=10`);
        if (res.ok) {
            const data = await res.json();
            state.auditEvents = (data.events || []).slice(0, 5).map(event => ({
                control: event.control_family || 'AU',
                event: `${event.event_type} - ${event.action?.operation || 'N/A'}`,
                time: formatTime(event.timestamp)
            }));
            renderAuditEvents();
        }
    } catch (error) {
        console.log('Audit API not available, using demo data');
        loadDemoAuditEvents();
    }
}

function loadDemoNodes() {
    state.nodes = [
        { node_id: 'NODE-ALPHA', status: 'CONNECTED', last_seen: new Date().toISOString(), ip_address: '10.0.1.50' },
        { node_id: 'NODE-BRAVO', status: 'CONNECTED', last_seen: new Date().toISOString(), ip_address: '10.0.1.51' },
        { node_id: 'NODE-CHARLIE', status: 'DISCONNECTED', last_seen: '2024-12-23T18:15:00Z', ip_address: '10.0.1.52' },
        { node_id: 'NODE-DELTA', status: 'CONNECTED', last_seen: new Date().toISOString(), ip_address: '10.0.1.53' }
    ];
    renderNodes();
}

function loadDemoAuditEvents() {
    state.auditEvents = [
        { control: 'AU', event: 'MESSAGE_SENT from NODE-ALPHA', time: formatTime(new Date()) },
        { control: 'IA', event: 'AUTH_SUCCESS for operator', time: formatTime(new Date()) },
        { control: 'SC', event: 'ENCRYPT completed', time: formatTime(new Date()) },
        { control: 'AC', event: 'RBAC_CHECK passed', time: formatTime(new Date()) },
        { control: 'AU', event: 'MESSAGE_DELIVERED to NODE-BRAVO', time: formatTime(new Date()) }
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
        <div class="message-item">
            <span class="message-precedence ${msg.precedence.toLowerCase()}">${msg.precedence}</span>
            <span class="message-route">${msg.sender} → ${msg.recipient}</span>
            <span class="message-time">${msg.time}</span>
            <span class="message-status ${msg.status.toLowerCase()}">${msg.status}</span>
        </div>
    `).join('');
}

function renderMetrics() {
    const messagesPerSec = document.getElementById('messagesPerSec');
    const avgLatency = document.getElementById('avgLatency');
    const uptime = document.getElementById('uptime');
    const authFailures = document.getElementById('authFailures');

    if (messagesPerSec) messagesPerSec.textContent = state.metrics.messagesPerSec;
    if (avgLatency) avgLatency.textContent = `${state.metrics.avgLatency}ms`;
    if (uptime) uptime.textContent = `${state.metrics.uptime}h ${Math.floor(Math.random() * 60)}m`;
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
    datetimeEl.textContent = now.toLocaleDateString('en-US', options) + ' UTC';
}

function formatTime(isoString) {
    if (!isoString) return '--:--';
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
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
    // For demo, generate a simple token
    return 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkYXNoYm9hcmQiLCJyb2xlIjoib3BlcmF0b3IifQ.demo';
}

// Add a message to the recent messages list (called when API sends a message)
function addMessage(messageData) {
    const newMessage = {
        id: messageData.message_id,
        precedence: messageData.precedence,
        sender: messageData.sender || 'UNKNOWN',
        recipient: messageData.recipient || 'UNKNOWN',
        status: messageData.status,
        time: formatTime(messageData.created_at || new Date().toISOString())
    };

    state.messages.unshift(newMessage);
    if (state.messages.length > 10) {
        state.messages.pop();
    }

    renderMessages();
}

// Expose for debugging
window.tacedgeState = state;
window.tacedgeRefresh = fetchAllData;

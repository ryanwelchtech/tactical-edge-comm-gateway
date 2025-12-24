/**
 * TacEdge Gateway - Tactical Operations Dashboard
 * Real-time visualization of tactical communications platform
 */

// Configuration
const CONFIG = {
    gatewayUrl: 'http://localhost:5000',
    refreshInterval: 5000,
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
    auditEvents: []
};

// Initialize Dashboard
document.addEventListener('DOMContentLoaded', () => {
    initializeDashboard();
    startDataRefresh();
    updateDateTime();
    setInterval(updateDateTime, 1000);
});

function initializeDashboard() {
    // Load initial demo data
    loadDemoData();
    
    // Render all components
    renderNodes();
    renderQueueStats();
    renderMessages();
    renderMetrics();
    renderServiceHealth();
    renderAuditEvents();
}

function loadDemoData() {
    // Demo nodes
    state.nodes = [
        { node_id: 'NODE-ALPHA', status: 'CONNECTED', last_seen: new Date().toISOString(), ip_address: '10.0.1.50' },
        { node_id: 'NODE-BRAVO', status: 'CONNECTED', last_seen: new Date().toISOString(), ip_address: '10.0.1.51' },
        { node_id: 'NODE-CHARLIE', status: 'DISCONNECTED', last_seen: '2024-12-23T18:15:00Z', ip_address: '10.0.1.52' },
        { node_id: 'NODE-DELTA', status: 'CONNECTED', last_seen: new Date().toISOString(), ip_address: '10.0.1.53' }
    ];
    
    // Demo queue status
    state.queueStatus = {
        FLASH: Math.floor(Math.random() * 3),
        IMMEDIATE: Math.floor(Math.random() * 10),
        PRIORITY: Math.floor(Math.random() * 25),
        ROUTINE: Math.floor(Math.random() * 100)
    };
    
    // Demo messages
    state.messages = [
        { id: 'msg-001', precedence: 'FLASH', sender: 'NODE-ALPHA', recipient: 'NODE-BRAVO', status: 'DELIVERED', time: '18:45:32' },
        { id: 'msg-002', precedence: 'IMMEDIATE', sender: 'NODE-BRAVO', recipient: 'NODE-DELTA', status: 'DELIVERED', time: '18:45:28' },
        { id: 'msg-003', precedence: 'PRIORITY', sender: 'NODE-ALPHA', recipient: 'NODE-CHARLIE', status: 'QUEUED', time: '18:45:15' },
        { id: 'msg-004', precedence: 'ROUTINE', sender: 'NODE-DELTA', recipient: 'NODE-ALPHA', status: 'DELIVERED', time: '18:44:52' },
        { id: 'msg-005', precedence: 'IMMEDIATE', sender: 'NODE-BRAVO', recipient: 'NODE-ALPHA', status: 'DELIVERED', time: '18:44:41' }
    ];
    
    // Demo metrics
    state.metrics = {
        messagesPerSec: Math.floor(Math.random() * 50) + 10,
        avgLatency: Math.floor(Math.random() * 100) + 20,
        uptime: Math.floor(Math.random() * 24),
        authFailures: Math.floor(Math.random() * 5)
    };
    
    // Demo services
    state.services = [
        { name: 'gateway-core', status: 'healthy' },
        { name: 'crypto-service', status: 'healthy' },
        { name: 'audit-service', status: 'healthy' },
        { name: 'store-forward', status: 'healthy' },
        { name: 'redis', status: 'healthy' }
    ];
    
    // Demo audit events
    state.auditEvents = [
        { control: 'AU', event: 'MESSAGE_SENT from NODE-ALPHA', time: '18:45:32' },
        { control: 'IA', event: 'AUTH_SUCCESS for operator', time: '18:45:30' },
        { control: 'SC', event: 'ENCRYPT completed', time: '18:45:29' },
        { control: 'AC', event: 'RBAC_CHECK passed', time: '18:45:28' },
        { control: 'AU', event: 'MESSAGE_DELIVERED to NODE-BRAVO', time: '18:45:27' }
    ];
}

function renderNodes() {
    const container = document.getElementById('nodeGrid');
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
    const maxQueue = 100;
    
    document.getElementById('flashCount').textContent = state.queueStatus.FLASH;
    document.getElementById('immediateCount').textContent = state.queueStatus.IMMEDIATE;
    document.getElementById('priorityCount').textContent = state.queueStatus.PRIORITY;
    document.getElementById('routineCount').textContent = state.queueStatus.ROUTINE;
    document.getElementById('totalQueued').textContent = total;
    
    // Update bars
    document.getElementById('flashBar').style.width = `${(state.queueStatus.FLASH / maxQueue) * 100}%`;
    document.getElementById('immediateBar').style.width = `${(state.queueStatus.IMMEDIATE / maxQueue) * 100}%`;
    document.getElementById('priorityBar').style.width = `${(state.queueStatus.PRIORITY / maxQueue) * 100}%`;
    document.getElementById('routineBar').style.width = `${(state.queueStatus.ROUTINE / maxQueue) * 100}%`;
}

function renderMessages() {
    const container = document.getElementById('messageList');
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
    document.getElementById('messagesPerSec').textContent = state.metrics.messagesPerSec;
    document.getElementById('avgLatency').textContent = `${state.metrics.avgLatency}ms`;
    document.getElementById('uptime').textContent = `${state.metrics.uptime}h ${Math.floor(Math.random() * 60)}m`;
    document.getElementById('authFailures').textContent = state.metrics.authFailures;
}

function renderServiceHealth() {
    const container = document.getElementById('serviceHealth');
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
    container.innerHTML = state.auditEvents.map(event => `
        <div class="audit-item">
            <span class="audit-control">${event.control}</span>
            <span class="audit-event">${event.event}</span>
            <span class="audit-time">${event.time}</span>
        </div>
    `).join('');
}

function updateDateTime() {
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
    document.getElementById('datetime').textContent = now.toLocaleDateString('en-US', options) + ' UTC';
}

function formatTime(isoString) {
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
}

function startDataRefresh() {
    setInterval(() => {
        // Simulate real-time updates
        simulateUpdates();
        renderQueueStats();
        renderMetrics();
    }, CONFIG.refreshInterval);
}

function simulateUpdates() {
    // Simulate queue changes
    state.queueStatus.FLASH = Math.max(0, state.queueStatus.FLASH + Math.floor(Math.random() * 3) - 1);
    state.queueStatus.IMMEDIATE = Math.max(0, state.queueStatus.IMMEDIATE + Math.floor(Math.random() * 5) - 2);
    state.queueStatus.PRIORITY = Math.max(0, state.queueStatus.PRIORITY + Math.floor(Math.random() * 7) - 3);
    state.queueStatus.ROUTINE = Math.max(0, state.queueStatus.ROUTINE + Math.floor(Math.random() * 15) - 7);
    
    // Simulate metric changes
    state.metrics.messagesPerSec = Math.max(0, state.metrics.messagesPerSec + Math.floor(Math.random() * 10) - 5);
    state.metrics.avgLatency = Math.max(10, state.metrics.avgLatency + Math.floor(Math.random() * 20) - 10);
}

// Fetch real data from API (for production use)
async function fetchData() {
    try {
        // Fetch nodes
        const nodesRes = await fetch(`${CONFIG.gatewayUrl}/api/v1/nodes`, {
            headers: { 'Authorization': `Bearer ${getToken()}` }
        });
        if (nodesRes.ok) {
            const data = await nodesRes.json();
            state.nodes = data.nodes;
            renderNodes();
        }
        
        // Fetch queue status
        const queueRes = await fetch(`${CONFIG.gatewayUrl.replace(':5000', ':5003')}/api/v1/queue/status`);
        if (queueRes.ok) {
            const data = await queueRes.json();
            state.queueStatus = {
                FLASH: data.queues.FLASH?.depth || 0,
                IMMEDIATE: data.queues.IMMEDIATE?.depth || 0,
                PRIORITY: data.queues.PRIORITY?.depth || 0,
                ROUTINE: data.queues.ROUTINE?.depth || 0
            };
            renderQueueStats();
        }
    } catch (error) {
        console.log('Using demo data - API not available');
    }
}

function getToken() {
    // In production, this would retrieve the JWT from storage
    return 'demo-token';
}


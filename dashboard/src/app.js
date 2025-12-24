/**
 * TacEdge Gateway - Tactical Operations Dashboard
 * Real-time visualization of tactical communications platform
 */

// Configuration
const CONFIG = {
    gatewayUrl: 'http://localhost:5000',
    storeForwardUrl: 'http://localhost:5003',
    auditUrl: 'http://localhost:5002',
    refreshInterval: 2000, // Refresh every 2 seconds for more real-time updates
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
    selectedMessage: null,
    messagesClearedAt: null,  // Timestamp when messages were last cleared (deprecated)
    clearedMessageIds: new Set(),  // IDs of messages that were cleared (better approach)
    dashboardInitTime: null  // Timestamp when dashboard was initialized - only show messages after this
};

// Initialize Dashboard
document.addEventListener('DOMContentLoaded', () => {
    initializeDashboard();
    initializeMessageSender();
    startDataRefresh();
    updateDateTime();
    setInterval(updateDateTime, 1000);
});

function initializeDashboard() {
    // Clear messages on first load/reload
    state.messages = [];
    state.allAuditEvents = [];
    
    // Set initialization time - only show messages created AFTER this time
    // This ensures no messages from previous sessions appear
    state.dashboardInitTime = Date.now();
    state.messagesClearedAt = null;
    state.clearedMessageIds = new Set();
    sessionStorage.removeItem('tacedge_messages_cleared_at');
    console.log(`[initializeDashboard] Starting fresh at ${new Date(state.dashboardInitTime).toISOString()} - only showing messages after this time`);
    
    renderMessages();

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

    // Extract messages from audit events (await to ensure it completes)
    await extractMessagesFromAudit();
}

async function fetchNodes() {
    try {
        const token = await getToken();
        const res = await fetch(`${CONFIG.gatewayUrl}/api/v1/nodes`, {
            headers: { 'Authorization': `Bearer ${token}` }
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
        // Fetch more events to ensure we catch all recent messages
        // Note: Audit service may require auth, but for demo we try without first
        const token = await getToken();
        const res = await fetch(`${CONFIG.auditUrl}/api/v1/audit/events?limit=200`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        if (res.ok) {
            const data = await res.json();
            const events = data.events || [];
            
            console.log(`[fetchAuditEvents] Fetched ${events.length} audit events`);

            // Show most recent 10 audit events (not just 5)
            state.auditEvents = events.slice(0, 10).map(event => ({
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
        } else {
            console.error(`[fetchAuditEvents] Failed to fetch: ${res.status} ${res.statusText}`);
        }
    } catch (error) {
        console.log('Audit API not available, using demo data');
        loadDemoAuditEvents();
    }
}

async function fetchMessageContent(messageId) {
    // Try to fetch message content from gateway API
    try {
        const token = await getToken();
        const url = `${CONFIG.gatewayUrl}/api/v1/messages/${encodeURIComponent(messageId)}/content`;
        const res = await fetch(url, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
            const data = await res.json();
            if (data.content) {
                console.log(`Successfully fetched content for ${messageId}`);
                return data.content;
            }
        } else {
            const errorText = await res.text();
            console.log(`Failed to fetch content for ${messageId}:`, res.status, errorText);
        }
    } catch (error) {
        console.log(`Could not fetch content for ${messageId}:`, error);
    }
    return null;
}

async function extractMessagesFromAudit() {
    // Extract ALL MESSAGE_SENT events from audit (not just first 5)
    const allEvents = state.allAuditEvents || [];
    
    // Debug: Log total events and MESSAGE_SENT count
    const messageSentEvents = allEvents.filter(e => e.event_type === 'MESSAGE_SENT');
    console.log(`[extractMessagesFromAudit] Total events: ${allEvents.length}, MESSAGE_SENT events: ${messageSentEvents.length}`);
    console.log(`[extractMessagesFromAudit] messagesClearedAt: ${state.messagesClearedAt}`);
    
    // First, filter by dashboard initialization time - only show messages created AFTER dashboard was loaded
    // This ensures no messages from previous sessions appear on first load
    // Note: This is only used on initial load, not after clearing
    let filteredEvents = allEvents;
    if (state.dashboardInitTime && state.clearedMessageIds.size === 0) {
        // Only apply init time filter if we haven't cleared messages yet
        // Once user clears, we rely on clearedMessageIds instead
        const initTime = state.dashboardInitTime;
        filteredEvents = allEvents.filter(e => {
            const eventTime = new Date(e.timestamp).getTime();
            return eventTime > initTime; // Only include events after dashboard initialization
        });
        console.log(`[extractMessagesFromAudit] After init time filter (${new Date(initTime).toISOString()}): ${filteredEvents.length} events (removed ${allEvents.length - filteredEvents.length} old events)`);
    } else if (state.dashboardInitTime && state.clearedMessageIds.size > 0) {
        // After clearing, we don't use init time filter - just use cleared IDs
        console.log(`[extractMessagesFromAudit] Skipping init time filter (messages were cleared, using ID filter instead)`);
    }
    
    // Then, filter out messages that were explicitly cleared by ID
    if (state.clearedMessageIds && state.clearedMessageIds.size > 0) {
        console.log(`[extractMessagesFromAudit] Filtering out ${state.clearedMessageIds.size} cleared message IDs`);
        const beforeClearFilter = filteredEvents.length;
        filteredEvents = filteredEvents.filter(e => {
            if (e.event_type === 'MESSAGE_SENT') {
                let messageId = e.action?.resource || '';
                if (messageId.startsWith('message:')) {
                    messageId = messageId.replace('message:', '');
                }
                if (!messageId || messageId === '') {
                    messageId = `msg-${e.event_id}`;
                }
                
                if (state.clearedMessageIds.has(messageId)) {
                    return false; // Filter out this specific message
                }
            }
            return true; // Keep all other events
        });
        console.log(`[extractMessagesFromAudit] After ID filter: ${filteredEvents.length} events (removed ${beforeClearFilter - filteredEvents.length})`);
    }
    
    // Filter for MESSAGE_SENT events
    const messageSentFiltered = filteredEvents.filter(e => e.event_type === 'MESSAGE_SENT');
    console.log(`[extractMessagesFromAudit] MESSAGE_SENT events after filtering: ${messageSentFiltered.length}`);
    
    if (messageSentFiltered.length > 0) {
        console.log(`[extractMessagesFromAudit] Sample MESSAGE_SENT event:`, {
            event_type: messageSentFiltered[0].event_type,
            timestamp: messageSentFiltered[0].timestamp,
            resource: messageSentFiltered[0].action?.resource,
            sender: messageSentFiltered[0].actor?.node_id,
            recipient: messageSentFiltered[0].context?.recipient
        });
    }
    
    const messageEvents = await Promise.all(
        messageSentFiltered
            .map(async e => {
                // Extract message ID - handle both "message:msg-xxx" and "msg-xxx" formats
                let messageId = e.action?.resource || '';
                if (messageId.startsWith('message:')) {
                    messageId = messageId.replace('message:', '');
                }
                if (!messageId || messageId === '') {
                    messageId = `msg-${e.event_id}`;
                }
                
                // Try to get content from audit context first
                let content = e.context?.content || e.context?.message_content;
                
                // If not in audit log, try fetching from gateway API
                if (!content || content === 'Message content not available') {
                    content = await fetchMessageContent(messageId);
                }
                
                // Fallback message
                if (!content || content === 'Message content not available') {
                    content = 'Message content not available';
                }
                
                return {
                    id: messageId,
                    precedence: e.context?.precedence || 'ROUTINE',
                    classification: e.context?.classification || 'UNCLASSIFIED',
                    sender: e.actor?.node_id || 'UNKNOWN',
                    recipient: e.context?.recipient || 'UNKNOWN',
                    content: content,
                    status: e.action?.outcome === 'SUCCESS' ? 'DELIVERED' : 'PENDING',
                    time: formatTime(e.timestamp),
                    timestamp: e.timestamp,
                    eventId: e.event_id,
                    raw: e
                };
            })
    );
    
    // Sort by newest first
    messageEvents.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

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
        console.log(`[extractMessagesFromAudit] Extracted ${state.messages.length} messages`);
        renderMessages();
    } else {
        console.log(`[extractMessagesFromAudit] No messages found in audit events`);
        // If no messages from audit, keep the list empty
        // Don't load demo data - user wants to see real messages only
        state.messages = [];
        renderMessages();
    }
}

function updateMetricsFromAudit(events) {
    // Count message events in the last minute
    const oneMinuteAgo = Date.now() - 60000;
    const recentMessages = events.filter(e => {
        const eventTime = new Date(e.timestamp).getTime();
        return e.event_type === 'MESSAGE_SENT' && eventTime > oneMinuteAgo;
    });

    // Calculate messages per second from recent activity
    if (recentMessages.length > 0) {
        const oldestTime = Math.min(...recentMessages.map(e => new Date(e.timestamp).getTime()));
        const timeSpan = (Date.now() - oldestTime) / 1000; // seconds
        state.metrics.messagesPerSec = timeSpan > 0 ? Math.round((recentMessages.length / timeSpan) * 10) / 10 : recentMessages.length;
    } else {
        // If no recent messages, show 0 or a small baseline
        state.metrics.messagesPerSec = 0;
    }

    // Calculate uptime
    const uptimeMs = Date.now() - state.startTime;
    const uptimeHours = Math.floor(uptimeMs / 3600000);
    const uptimeMinutes = Math.floor((uptimeMs % 3600000) / 60000);
    state.metrics.uptime = uptimeHours;
    state.metrics.uptimeMinutes = uptimeMinutes;

    // Count auth failures from audit events
    const authFailures = events.filter(e => 
        e.event_type === 'AUTH_FAILURE' || 
        (e.event_type === 'AUTH' && e.action?.outcome === 'FAILURE')
    ).length;
    state.metrics.authFailures = authFailures;

    // Calculate average latency from events with latency data
    const latencyEvents = events.filter(e => e.context?.latency_ms);
    if (latencyEvents.length > 0) {
        const totalLatency = latencyEvents.reduce((sum, e) => sum + (e.context.latency_ms || 0), 0);
        state.metrics.avgLatency = Math.round(totalLatency / latencyEvents.length);
    } else {
        // Fallback to reasonable default
        state.metrics.avgLatency = 45;
    }

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

async function showMessageModal(message) {
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
    document.getElementById('modalStatus').textContent = message.status;
    document.getElementById('modalStatus').className = `message-status ${message.status.toLowerCase()}`;
    document.getElementById('modalTime').textContent = formatTime(message.timestamp);
    document.getElementById('modalEventId').textContent = message.eventId || 'N/A';
    
    // If content is not available or is placeholder, try fetching from API
    let content = message.content;
    if (!content || content === 'Message content not available' || content === 'Message content not available in audit log') {
        document.getElementById('modalContent').textContent = 'Loading content...';
        content = await fetchMessageContent(message.id);
        if (!content) {
            content = 'Message content not available';
        }
    }
    document.getElementById('modalContent').textContent = content;

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

let sessionToken = null;
let sessionNodeId = null;

async function getToken() {
    // Generate unique token per session if not already generated
    if (!sessionToken) {
        try {
            const response = await fetch(`${CONFIG.gatewayUrl}/api/v1/auth/token`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            if (response.ok) {
                const data = await response.json();
                sessionToken = data.token;
                sessionNodeId = data.node_id;
                // Store in sessionStorage for persistence across page refreshes
                sessionStorage.setItem('tacedge_token', sessionToken);
                sessionStorage.setItem('tacedge_node_id', sessionNodeId);
                console.log('Generated new session token:', sessionNodeId);
            } else {
                console.warn('Failed to generate token, using fallback');
                sessionToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkYXNoYm9hcmQiLCJyb2xlIjoib3BlcmF0b3IifQ.demo';
            }
        } catch (error) {
            console.warn('Token generation failed, using fallback:', error);
            sessionToken = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkYXNoYm9hcmQiLCJyb2xlIjoib3BlcmF0b3IifQ.demo';
        }
    }
    
    // Check sessionStorage for existing token
    if (!sessionToken) {
        const stored = sessionStorage.getItem('tacedge_token');
        if (stored) {
            sessionToken = stored;
            sessionNodeId = sessionStorage.getItem('tacedge_node_id');
        }
    }
    
    return sessionToken;
}

// Message Sender Functions
async function sendMessage(precedence, classification, sender, recipient, content, isBatch = false, batchCount = 1) {
    const token = await getToken();
    const statusEl = document.getElementById('sendStatus');
    
    if (!content || content.trim() === '') {
        statusEl.textContent = 'Error: Message content is required';
        statusEl.className = 'send-status error';
        return;
    }
    
    const messages = [];
    const totalMessages = isBatch ? batchCount : 1;
    
    statusEl.textContent = `Sending ${totalMessages} message(s)...`;
    statusEl.className = 'send-status info';
    
    for (let i = 0; i < totalMessages; i++) {
        const messageContent = isBatch ? `${content} [Batch ${i + 1}/${totalMessages}]` : content;
        
        try {
            const response = await fetch(`${CONFIG.gatewayUrl}/api/v1/messages`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    precedence: precedence,
                    classification: classification,
                    sender: sender,
                    recipient: recipient,
                    content: messageContent,
                    ttl: 300
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                messages.push({ success: true, id: data.message_id });
            } else {
                const error = await response.json();
                messages.push({ success: false, error: error.detail?.error?.message || 'Failed' });
            }
        } catch (error) {
            messages.push({ success: false, error: error.message });
        }
        
        // Small delay between batch messages
        if (isBatch && i < totalMessages - 1) {
            await new Promise(resolve => setTimeout(resolve, 100));
        }
    }
    
    const successCount = messages.filter(m => m.success).length;
    const failCount = messages.filter(m => !m.success).length;
    
    if (failCount === 0) {
        statusEl.textContent = `Successfully sent ${successCount} message(s)!`;
        statusEl.className = 'send-status success';
        // Clear form
        if (!isBatch) {
            document.getElementById('messageContent').value = '';
        }
        // Refresh data immediately, then again after delays to catch audit events
        // Audit service may need time to persist events
        console.log(`[sendMessage] Message sent successfully, refreshing data...`);
        fetchAllData();
        setTimeout(() => {
            console.log(`[sendMessage] First refresh (500ms delay)`);
            fetchAllData();
        }, 500);
        setTimeout(() => {
            console.log(`[sendMessage] Second refresh (2s delay)`);
            fetchAllData();
        }, 2000);
        setTimeout(() => {
            console.log(`[sendMessage] Third refresh (5s delay)`);
            fetchAllData();
        }, 5000);
    } else {
        statusEl.textContent = `Sent ${successCount}/${totalMessages} message(s). ${failCount} failed.`;
        statusEl.className = 'send-status error';
    }
}

function initializeMessageSender() {
    const sendBtn = document.getElementById('sendMessageBtn');
    const batchBtn = document.getElementById('sendBatchBtn');
    const clearBtn = document.getElementById('clearMessagesBtn');
    
    if (sendBtn) {
        sendBtn.addEventListener('click', async () => {
            const precedence = document.getElementById('senderPrecedence').value;
            const classification = document.getElementById('senderClassification').value;
            const sender = document.getElementById('senderNode').value;
            const recipient = document.getElementById('recipientNode').value;
            const content = document.getElementById('messageContent').value;
            
            sendBtn.disabled = true;
            await sendMessage(precedence, classification, sender, recipient, content, false);
            sendBtn.disabled = false;
        });
    }
    
    if (batchBtn) {
        batchBtn.addEventListener('click', async () => {
            const precedence = document.getElementById('senderPrecedence').value;
            const classification = document.getElementById('senderClassification').value;
            const sender = document.getElementById('senderNode').value;
            const recipient = document.getElementById('recipientNode').value;
            const content = document.getElementById('messageContent').value;
            const batchCount = parseInt(document.getElementById('batchCount').value) || 1;
            
            if (batchCount < 1 || batchCount > 50) {
                const statusEl = document.getElementById('sendStatus');
                statusEl.textContent = 'Error: Batch count must be between 1 and 50';
                statusEl.className = 'send-status error';
                return;
            }
            
            batchBtn.disabled = true;
            await sendMessage(precedence, classification, sender, recipient, content, true, batchCount);
            batchBtn.disabled = false;
        });
    }
    
    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            // Clear all messages and audit events
            // Store the IDs of messages that were visible when cleared
            const clearedMessageIds = new Set(state.messages.map(m => m.id));
            state.messages = [];
            state.allAuditEvents = [];
            
            // Add cleared message IDs to the set (don't reset init time - that would filter out new messages!)
            // Just track which specific messages were cleared
            clearedMessageIds.forEach(id => state.clearedMessageIds.add(id));
            
            console.log(`[clearMessages] Cleared ${clearedMessageIds.size} message(s) by ID. Total cleared: ${state.clearedMessageIds.size}`);
            
            // Don't persist clear timestamp - just clear the current view
            sessionStorage.removeItem('tacedge_messages_cleared_at');
            state.messagesClearedAt = null;
            
            renderMessages();
        });
    }
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

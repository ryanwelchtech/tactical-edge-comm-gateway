# Tactical Operations Dashboard - User Guide

## Overview

The Tactical Operations Dashboard provides a real-time interface for monitoring and managing the TacEdge Gateway communications platform. The dashboard displays network node status, message queues, system metrics, and allows you to send messages directly from the web interface.

**📹 Demo Videos:**
- **[Dashboard Demo](images/dashboard-demo.gif)** - Full dashboard walkthrough
- **[API Demo](images/api-demo.gif)** - Sending messages via REST API

## Accessing the Dashboard

1. **Start the system:**
   ```bash
   docker-compose up -d
   ```

2. **Open your browser:**
   Navigate to `http://localhost:8081`

3. **Initial State:**
   - Dashboard starts with no messages displayed
   - All nodes show as "CONNECTED"
   - Queue counts start at 0
   - System metrics initialize to baseline values

## Dashboard Layout

The dashboard is organized into three main columns:

### Left Column

#### Network Nodes Panel
- **Purpose:** Displays the status of all tactical network nodes
- **Information Shown:**
  - Node ID (e.g., NODE-ALPHA, NODE-BRAVO)
  - IP Address
  - Connection Status (CONNECTED/DISCONNECTED)
  - Last Seen Timestamp
- **Updates:** Refreshes every 2 seconds

#### System Metrics Panel
- **Purpose:** Real-time system performance indicators
- **Metrics Displayed:**
  - **Messages/sec:** Current message processing rate
  - **Avg Latency:** Average message processing latency
  - **Uptime:** System uptime since last restart
  - **Auth Failures:** Count of authentication failures
- **Service Health:**
  - Lists all microservices and their health status
  - Green "HEALTHY" indicates service is operational
- **Recent Audit Events:**
  - Shows last 10 audit events
  - Displays event type, action, and timestamp
  - Scrollable list for viewing more events

### Center Column (Main Panel)

#### Message Queue Status
- **Purpose:** Monitor message queues by precedence level
- **Queue Types:**
  - **FLASH** (Red): Highest priority, <100ms latency
  - **IMMEDIATE** (Orange): High priority, <500ms latency
  - **PRIORITY** (Green): Medium priority, <2s latency
  - **ROUTINE** (Blue): Standard priority, best effort
- **Total Queued:** Sum of all messages across all queues
- **Updates:** Real-time queue depth monitoring

#### Recent Messages
- **Purpose:** View recently delivered messages
- **Information Displayed:**
  - Message precedence (color-coded tag)
  - Sender → Recipient nodes
  - Timestamp
  - Delivery status (DELIVERED/PENDING)
- **Interactions:**
  - **Click any message** to view full details in a modal
  - **Clear Button:** Removes all messages from the list
    - Messages stay cleared until new ones are sent
    - Only messages created after clearing will appear
- **Updates:** Automatically updates when new messages are sent

### Right Column

#### Send Message Panel
- **Purpose:** Send messages directly from the dashboard
- **Form Fields:**
  - **Precedence:** Select message priority (FLASH, IMMEDIATE, PRIORITY, ROUTINE)
  - **Classification:** Select classification level (UNCLASSIFIED, CONFIDENTIAL, SECRET, TOP_SECRET)
  - **Sender:** Select source node from dropdown
  - **Recipient:** Select destination node from dropdown
  - **Content:** Enter message text (required)
  - **Batch Count (Optional):** Number of messages to send (1-50)
- **Actions:**
  - **Send Message:** Sends a single message
  - **Send Batch:** Sends multiple messages (uses batch count)
- **Status Feedback:**
  - Success/error messages appear below buttons
  - Messages appear in "Recent Messages" within 2 seconds

## How to Use

### Sending a Single Message

1. **Fill in the form:**
   - Select precedence (e.g., FLASH for urgent messages)
   - Choose classification level
   - Select sender and recipient nodes
   - Enter message content

2. **Click "Send Message"**
   - Button shows loading state while sending
   - Success message appears when complete
   - Message appears in "Recent Messages" list

3. **View the message:**
   - Click on the message in "Recent Messages" to see full details
   - Modal shows: Message ID, precedence, classification, sender, recipient, content, timestamp, and status

### Sending Batch Messages

1. **Fill in the form** (same as single message)

2. **Set Batch Count:**
   - Enter a number between 1 and 50
   - Each message will have `[Batch X/Y]` appended to content

3. **Click "Send Batch"**
   - All messages are sent sequentially
   - Progress shown in status area
   - Messages appear in queue and Recent Messages

### Viewing Message Details

1. **Click any message** in the "Recent Messages" list
2. **Modal displays:**
   - Complete message information
   - Full message content
   - Event ID and audit trail information
   - Timestamp and delivery status
3. **Close modal:** Click the X button or click outside the modal

### Clearing Messages

1. **Click the "Clear" button** next to "Recent Messages" title
2. **All messages are removed** from the list
3. **Messages stay cleared:**
   - Old messages won't reappear on refresh
   - Only new messages sent after clearing will appear
   - Useful for starting fresh during demos

### Monitoring System Health

- **Network Nodes:** All nodes should show "CONNECTED" status
- **Service Health:** All services should show "HEALTHY"
- **Queue Status:** Monitor queue depths for each precedence level
- **System Metrics:** Track performance indicators in real-time

## Real-Time Updates

The dashboard automatically refreshes every 2 seconds to show:
- Latest message queue depths
- New messages in Recent Messages
- Updated system metrics
- Service health status
- Network node last-seen timestamps

## Priority-Based Queuing

The system implements **military-standard priority-based message queuing** where messages are automatically processed in strict precedence order.

### How It Works

1. **Separate Queues**: Each precedence level (FLASH, IMMEDIATE, PRIORITY, ROUTINE) has its own dedicated queue
2. **Priority Processing**: A background worker processes queues every 2 seconds in strict order:
   - FLASH messages process first (highest priority)
   - Then IMMEDIATE
   - Then PRIORITY
   - Finally ROUTINE (lowest priority)
3. **Queue Visualization**: The "Message Queue Status" panel shows real-time queue depths for each precedence level

### Demonstrating Priority Queuing

**Test Scenario:**

1. **Send messages in reverse priority order:**
   - Send a ROUTINE message
   - Send a PRIORITY message
   - Send an IMMEDIATE message
   - Send a FLASH message

2. **Observe the queues:**
   - Watch queue counts increase in the "Message Queue Status" panel
   - All four queues will show 1 message each

3. **Watch automatic processing:**
   - Within 2 seconds, FLASH processes first (count → 0)
   - Then IMMEDIATE (count → 0)
   - Then PRIORITY (count → 0)
   - Finally ROUTINE (count → 0)

4. **Verify in Recent Messages:**
   - Messages appear in **processing order** (not send order)
   - FLASH appears first, even though it was sent last
   - Followed by IMMEDIATE, PRIORITY, then ROUTINE

**Key Takeaway:** Higher precedence messages **always** process before lower precedence, regardless of when they were sent.

## Tips

- **Message Precedence:** Use FLASH for critical alerts, ROUTINE for standard communications
- **Priority Queuing:** Send messages with different precedence levels to see priority-based processing in action
- **Batch Sending:** Useful for testing queue behavior and load scenarios
- **Clear Messages:** Use before demos to start with a clean slate
- **Message Details:** Click any message to see full content and metadata
- **Real-time Monitoring:** Watch queue depths change as messages are processed

## Troubleshooting

### Messages Not Appearing
- Check that services are running: `docker-compose ps`
- Verify service health indicators show "HEALTHY"
- Check browser console for API errors
- Ensure you're sending messages with valid node IDs

### Clear Button Not Working
- Refresh the page if messages reappear
- Check browser console for JavaScript errors
- Verify dashboard JavaScript is loading correctly

### Dashboard Not Loading
- Verify Docker containers are running: `docker-compose ps`
- Check dashboard container logs: `docker-compose logs dashboard`
- Ensure port 8081 is not in use by another application

## Keyboard Shortcuts

- **Escape:** Close message detail modal
- **Click outside modal:** Close message detail modal

## Browser Compatibility

- **Recommended:** Chrome, Firefox, Edge (latest versions)
- **Mobile:** Responsive design works on tablets and mobile devices
- **Screen Size:** Optimized for desktop (1920x1080+) and tablet (768px+)


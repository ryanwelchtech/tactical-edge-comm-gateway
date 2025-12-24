# Demo GIFs

This directory contains demonstration GIFs for the Tactical Edge Communications Gateway project.

## Required GIFs

### 1. `dashboard-demo.gif`
**Purpose:** Demonstrates the tactical operations dashboard in action

**Should show:**
- Dashboard loading with no messages
- Sending messages via the web form
- Real-time queue updates
- Priority-based message processing
- Message detail modal
- System metrics and node health
- Clear messages functionality

**Duration:** 30-60 seconds recommended

### 2. `api-demo.gif`
**Purpose:** Demonstrates sending messages via the REST API

**Should show:**
- Generating a JWT token using `generate-jwt.py`
- Sending a message via `curl` command
- Message appearing in the dashboard
- Different precedence levels (FLASH, IMMEDIATE, PRIORITY, ROUTINE)
- Queue processing in action

**Duration:** 30-45 seconds recommended

## Creating the GIFs

### Tools
- **Screen Recording:** OBS Studio, ShareX (Windows), or built-in screen recorder
- **GIF Conversion:** 
  - [gifski](https://gif.ski/) - High quality
  - [FFmpeg](https://ffmpeg.org/) - Command line
  - Online converters (ezgif.com, etc.)

### Tips
- Keep file sizes reasonable (< 5MB each)
- Use 60 FPS for smooth playback
- Crop to relevant areas only
- Add text annotations if helpful
- Show clear transitions between steps

## Usage

These GIFs are referenced in:
- `README.md` - Main project documentation
- `docs/UI_GUIDE.md` - Dashboard user guide
- `docs/API.md` - API documentation
- `docs/OPERATIONS.md` - Operations runbook
- `docs/LINKEDIN_POST.md` - LinkedIn post content


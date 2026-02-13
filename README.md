# 🛡️ A10 Guardian

REST API + MCP Server for A10 Networks Thunder TPS DDoS mitigation devices. Provides a simplified interface to manage protected zones, monitor active incidents, and deploy mitigation configurations — accessible via HTTP endpoints or AI agents through the Model Context Protocol (MCP).

## ✨ Features

- **🚀 REST API** — Mitigation zones, system monitoring, incident tracking, template management
- **🤖 MCP Server** — AI-agent integration via Model Context Protocol (Claude Desktop, n8n, etc.)
- **📝 Configurable Templates** — JSON-based zone templates with custom profiles, policies, and services
- **📥 Template Import** — Import configurations from existing A10 zones to reuse across new mitigations
- **🔐 Authentication** — API token for REST, Bearer token for MCP HTTP transport
- **📊 Observability** — Structured logging with Loguru, audit trail for write operations
- **🔔 Notifications** — Granular webhook alerts (Slack, Discord) for templates, mitigations, and system events
- **🐳 Docker Ready** — Two-service Compose setup (API + MCP) with health checks and persistent template storage

## 🛠️ Tech Stack

- **🐍 Python 3.10+** / **⚡ FastAPI** / **🦄 Uvicorn**
- **🔌 FastMCP** — MCP server with stdio and streamable-http transports
- **🌐 httpx** — HTTP client for A10 device communication
- **✅ Pydantic v2** — Request/response validation
- **📝 Loguru** — Structured logging with rotation
- **⏱️ SlowAPI** — Rate limiting

## 🚀 Quick Start (Docker)

### Option 1: Using Pre-built Image (Recommended)

**Docker Compose:**
```bash
# 1. Download compose file
curl -O https://raw.githubusercontent.com/opastorello/a10-guardian/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/opastorello/a10-guardian/main/.env.example

# 2. Configure
cp .env.example .env
# Edit .env with your A10 credentials

# 3. Pull and start
docker compose pull
docker compose up -d
```

**Direct Docker Run:**
```bash
# Pull the image
docker pull ghcr.io/opastorello/a10-guardian:latest

# Run REST API server
docker run -d \
  --name a10-guardian-api \
  -p 8000:8000 \
  -e A10_USERNAME=admin \
  -e A10_PASSWORD=your_password \
  -e A10_BASE_URL=https://your-a10-host:17489 \
  -e API_SECRET_TOKEN=your_secret_token \
  -e WEBHOOK_ENABLED=true \
  -e WEBHOOK_URL=https://discord.com/api/webhooks/your-webhook \
  -e NOTIFY_ATTACK_DETECTED=true \
  -e NOTIFY_ATTACK_MITIGATED=true \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/config:/app/config \
  --restart unless-stopped \
  ghcr.io/opastorello/a10-guardian:latest

# Run MCP Server (optional - for AI agent integration)
docker run -d \
  --name a10-guardian-mcp \
  -p 8001:8001 \
  -e A10_USERNAME=admin \
  -e A10_PASSWORD=your_password \
  -e A10_BASE_URL=https://your-a10-host:17489 \
  -e API_SECRET_TOKEN=your_secret_token \
  -e MCP_TRANSPORT=streamable-http \
  -e MCP_HOST=0.0.0.0 \
  -e MCP_PORT=8001 \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/config:/app/config \
  --restart unless-stopped \
  ghcr.io/opastorello/a10-guardian:latest \
  python src/a10_guardian/mcp_server.py
```

**Common Environment Variables:**
```bash
# Required
A10_USERNAME=admin                               # A10 device username
A10_PASSWORD=your_password                       # A10 device password
A10_BASE_URL=https://your-a10-host:17489       # A10 device URL
API_SECRET_TOKEN=your_secret_token              # API authentication token

# Optional - Webhooks
WEBHOOK_ENABLED=true                            # Enable webhook notifications
WEBHOOK_URL=https://discord.com/api/webhooks/...  # Discord/Slack webhook URL
WEBHOOK_USERNAME=A10 Guardian                   # Bot display name

# Optional - Attack Monitoring
NOTIFY_ATTACK_DETECTED=true                     # Alert on new attacks
NOTIFY_ATTACK_MITIGATED=true                    # Alert when attacks end
NOTIFY_ATTACK_ONGOING=false                     # Periodic updates (15min)
ATTACK_MONITORING_INTERVAL=30                   # Check interval (seconds)

# Optional - Mitigation Notifications
NOTIFY_MITIGATION_START=true                    # Alert on mitigation start
NOTIFY_MITIGATION_STOP=true                     # Alert on mitigation stop

# Optional - Template Notifications
NOTIFY_TEMPLATE_CREATE=true                     # Alert on template creation
NOTIFY_TEMPLATE_IMPORT=true                     # Alert on template import
```

### Option 2: Build from Source

```bash
# 1. Clone and configure
git clone https://github.com/opastorello/a10-guardian.git
cd a10-guardian
cp .env.example .env
# Edit .env with your A10 credentials

# 2. Build and start
docker compose up --build -d
```

| Service | Port | URL |
|---------|------|-----|
| REST API | 8000 | `http://localhost:8000/docs` |
| MCP Server | 8001 | `http://localhost:8001/mcp` |

## 💻 Running Locally

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install
pip install -e .

# Start API server
uvicorn a10_guardian.main:app --reload

# Start MCP server (separate terminal)
MCP_TRANSPORT=streamable-http MCP_PORT=8001 python src/a10_guardian/mcp_server.py
```

## 🔌 API Endpoints

All endpoints require the `x-api-token` header. Interactive docs available at `/docs`.

### 🖥️ System

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/system/info` | Hostname, version, serial, uptime |
| GET | `/api/v1/system/devices` | All devices in inventory |
| GET | `/api/v1/system/license` | License type, limits, expiration |

### 🛡️ Mitigation

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/mitigation/zones/mitigate/{ip}?template=default` | Create/deploy zone using specified template |
| GET | `/api/v1/mitigation/zones/list` | Paginated list of zones |
| GET | `/api/v1/mitigation/zones/status/{ip}` | Full zone config by IP |
| DELETE | `/api/v1/mitigation/zones/remove/{ip}` | Stop mitigation and delete zone |

### 📝 Templates

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/templates/list` | List all configured templates |
| GET | `/api/v1/templates/{name}` | Get template details |
| POST | `/api/v1/templates/{name}` | Create or update template |
| POST | `/api/v1/templates/validate` | Validate template without saving (dry-run) |
| DELETE | `/api/v1/templates/{name}` | Delete template |
| GET | `/api/v1/templates/export/{name}` | Download template as JSON file |
| POST | `/api/v1/templates/import/{ip}?name={name}` | Import template from existing A10 zone |

### 🚨 Attack Monitoring

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/attacks/ongoing` | List all ongoing DDoS attacks (paginated) |
| GET | `/api/v1/attacks/incident/{id}/stats` | Get traffic statistics for specific incident |
| GET | `/api/v1/attacks/incident/{id}/details` | Get full incident details and raw data |

### ❤️ Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (optional `?check_upstream=true`) |

## 📝 Template System

### 📋 Overview

Templates are JSON configurations that define how zones are created and monitored. They contain:

- **📦 Zone Payload**: Profile, policy, device group, and service list
- **📊 Monitor Payload**: Detection algorithm, sensitivity, and per-protocol thresholds

Templates are stored in `config/zone_templates/` (excluded from Git for security).

### ⚙️ Initial Setup

#### Option 1: Import from existing zone (recommended)

```bash
curl -X POST "http://localhost:8000/api/v1/templates/import/203.0.113.5?name=default" \
  -H "x-api-token: YOUR_TOKEN"
```

#### Option 2: Create manually

```bash
curl -X POST "http://localhost:8000/api/v1/templates/default" \
  -H "x-api-token: YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d @docs/examples/gaming-template.json
```

### Using Templates

Once configured, specify the template when creating mitigations:

```bash
# Use default template
POST /api/v1/mitigation/zones/mitigate/203.0.113.10

# Use specific template
POST /api/v1/mitigation/zones/mitigate/203.0.113.10?template=gaming
```

All zones created from the same template will have identical configurations (profiles, policies, services).

## 🚨 Real-Time Attack Monitoring

A10 Guardian provides automated real-time monitoring of DDoS attacks across **all protected zones** (not just those created via API). The system continuously polls the A10 device for active incidents and sends instant notifications when attacks are detected or mitigated.

### ⚙️ How It Works

- **🔍 Background monitoring task** checks for ongoing attacks every 10 seconds (configurable)
- **🌍 Monitors ALL zones** in the A10 device, regardless of how they were created
- **🚨 Detects new attacks** and sends instant notifications (🚨 Attack Detected)
- **⏱️ Tracks attack duration** and sends notifications when attacks end (✅ Attack Mitigated)
- **⚠️ Optional periodic updates** for long-running attacks (⚠️ Attack Ongoing every 15 min)

### ⚙️ Configuration

Enable attack monitoring in `.env`:

```bash
# Attack Monitoring (real-time DDoS attack detection)
NOTIFY_ATTACK_DETECTED=True       # Alert when DDoS attack is detected
NOTIFY_ATTACK_MITIGATED=True      # Alert when attack is mitigated/ended
NOTIFY_ATTACK_ONGOING=False       # Periodic updates for long-running attacks (every 15min)
ATTACK_MONITORING_INTERVAL=30     # Check for attacks every N seconds (min: 10, max: 300)
```

### 🔔 Webhook Notifications

When `WEBHOOK_ENABLED=true`, attack events are sent to Discord/Slack/n8n:

**Attack Detected:**
```json
{
  "title": "🚨 Attack Detected",
  "description": "DDoS attack detected on 203.0.113.50",
  "color": 16711680,  // Red
  "fields": [
    {"name": "Zone", "value": "203.0.113.50"},
    {"name": "Severity", "value": "High"},
    {"name": "Incident ID", "value": "a1b2c3d4-..."}
  ]
}
```

**Attack Mitigated:**
```json
{
  "title": "✅ Attack Mitigated",
  "description": "Attack on 203.0.113.50 has been mitigated",
  "color": 65280,  // Green
  "fields": [
    {"name": "Zone", "value": "203.0.113.50"},
    {"name": "Duration", "value": "8 minutes 42 seconds"}
  ]
}
```

### API Endpoints

Query attack data programmatically:

```bash
# List all ongoing attacks
GET /api/v1/attacks/ongoing?page=1&items=20

# Get detailed statistics for specific attack
GET /api/v1/attacks/incident/{incident_id}/stats

# Get full incident details with raw A10 data
GET /api/v1/attacks/incident/{incident_id}/details
```

**Example Response (Ongoing Attacks):**
```json
{
  "total": 2,
  "page": 1,
  "items_per_page": 20,
  "incidents": [
    {
      "incident_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "zone_name": "203.0.113.50",
      "zone_id": "f6593c0b-9c93-4736-babc-8a3828e35af6",
      "severity": "High",
      "start_time": "2026-02-13T10:15:30Z",
      "status": "Ongoing"
    }
  ]
}
```

**Example Response (Incident Stats):**
```json
{
  "incident_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "zone_name": "203.0.113.50",
  "total_packets": 15000000,
  "total_bytes": 7500000000,
  "peak_pps": 500000,
  "peak_bps": 4000000000,
  "attack_vectors": [
    {"protocol": "UDP", "port": 53, "percentage": 65},
    {"protocol": "TCP", "port": 80, "percentage": 25},
    {"protocol": "ICMP", "port": null, "percentage": 10}
  ]
}
```

### 🎯 Monitoring Scope

**What's Currently Monitored:**

- ✅ **All ongoing DDoS attacks** — Real-time incident detection across the entire A10 device
- ✅ **Any protected zone** — Monitors zones regardless of origin:
  - Zones created via this API
  - Zones created manually in the A10 TPS web interface
  - Zones created by other systems or automation

**What's NOT Currently Monitored** (see [Roadmap](#-roadmap)):

- ⏳ **Zone creation/deletion** — When zones are added/removed outside the API
- ⏳ **Zone configuration changes** — When zones are manually modified in the A10 interface
- ⏳ **Template drift detection** — When deployed zones differ from their original templates

This provides **complete visibility** into all DDoS activity. For infrastructure change monitoring (zones, configs), see planned enhancements in the Roadmap section.

## 🤖 MCP Integration

The MCP server exposes 9 tools for AI agents:

#### 🖥️ System & Monitoring

| Tool                                 | Description                                           |
|--------------------------------------|-------------------------------------------------------|
| `get_system_health()`                | Check if the A10 device is online                     |
| `list_active_mitigations()`          | List all IPs currently under mitigation               |
| `get_zone_status(ip_address)`        | Full config and status of a specific zone             |

#### 🛡️ Mitigation Management

| Tool                                     | Description                                              |
|------------------------------------------|----------------------------------------------------------|
| `mitigate_ip(ip_address, template)`      | Create or re-sync mitigation using specified template    |
| `remove_mitigation(ip_address)`          | Stop mitigation and remove the zone                      |

#### 📝 Template Management

| Tool                                     | Description                                              |
|------------------------------------------|----------------------------------------------------------|
| `list_zone_templates()`                  | List all available templates                             |
| `get_zone_template(name)`                | Retrieve template configuration                          |
| `set_zone_template(template_json, name)` | Create/update template with validation                   |
| `import_zone_template(ip_address, name)` | Import template from existing A10 zone                   |

### Connecting via n8n (HTTP)

Use the **MCP Client Tool** node with:

- **URL:** `http://<host>:8001/mcp`
- **Authentication:** Bearer Token
- **Token:** Your `API_SECRET_TOKEN` value

### Connecting via Claude Desktop (stdio)

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "a10-guardian": {
      "command": "python",
      "args": ["src/a10_guardian/mcp_server.py"],
      "cwd": "/path/to/a10-guardian",
      "env": {
        "A10_USERNAME": "admin",
        "A10_PASSWORD": "your_password",
        "API_SECRET_TOKEN": "your_token",
        "A10_BASE_URL": "https://your-a10-host:17489"
      }
    }
  }
}
```

See [docs/MCP_USAGE.md](docs/MCP_USAGE.md) for the full MCP integration guide.

## 🔐 Authentication

| Interface | Header | Format |
|-----------|--------|--------|
| REST API | `x-api-token` | Plain token value |
| MCP (HTTP) | `Authorization` | `Bearer <token>` |

Both use the same `API_SECRET_TOKEN` from `.env`.

## ⚙️ Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| **A10 Device** | | |
| `A10_USERNAME` | A10 device username | *required* |
| `A10_PASSWORD` | A10 device password | *required* |
| `A10_BASE_URL` | Full URL to A10 device | `https://A10_HOST:A10_PORT` |
| `A10_VERIFY_SSL` | Verify SSL certificates | `False` |
| **API Settings** | | |
| `API_SECRET_TOKEN` | Auth token for API and MCP | *required* |
| `DEBUG` | Enable debug mode | `False` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `RATE_LIMIT_DEFAULT` | API rate limit | `60/minute` |
| **Webhooks** | | |
| `WEBHOOK_ENABLED` | Enable webhook notifications | `False` |
| `WEBHOOK_URL` | Slack/Discord/n8n webhook URL | — |
| `WEBHOOK_USERNAME` | Display name for webhook messages | `A10 Guardian` |
| `WEBHOOK_FOOTER` | Footer text for webhook messages | `A10 Guardian API` |
| **Notification Control** | | |
| `NOTIFY_TEMPLATE_CREATE` | Notify on template creation | `True` |
| `NOTIFY_TEMPLATE_UPDATE` | Notify on template updates | `False` |
| `NOTIFY_TEMPLATE_DELETE` | Notify on template deletion | `True` |
| `NOTIFY_TEMPLATE_IMPORT` | Notify on template imports | `True` |
| `NOTIFY_MITIGATION_START` | Notify when mitigation starts | `True` |
| `NOTIFY_MITIGATION_STOP` | Notify when mitigation stops | `True` |
| `NOTIFY_SYSTEM_HEALTH` | Monitor A10 health (60s interval) | `False` |
| **Attack Monitoring** | | |
| `NOTIFY_ATTACK_DETECTED` | Alert when attack is detected | `True` |
| `NOTIFY_ATTACK_MITIGATED` | Alert when attack ends | `True` |
| `NOTIFY_ATTACK_ONGOING` | Periodic updates for long attacks | `False` |
| `ATTACK_MONITORING_INTERVAL` | Check interval in seconds (10-300) | `30` |

## 🚧 Roadmap

Planned enhancements for future releases:

### 🔔 Enhanced Monitoring

- **Zone Change Detection** — Monitor and notify when zones are created, modified, or deleted directly in the A10 device (outside API/MCP)
  - Real-time alerts when zones appear/disappear from the A10 inventory
  - Configuration drift detection (when zones are manually modified)
  - Reconciliation suggestions when external changes are detected

- **Advanced Attack Analytics** — Historical attack data with pattern recognition
  - Attack frequency trends and heatmaps
  - Top attacked services and ports
  - Automatic baseline learning for anomaly detection

### ⚡ Performance & Scale

- **Batch Zone Operations** — Create/update multiple zones in a single API call
- **Zone Grouping** — Organize zones by customer, environment, or service type
- **Async Background Tasks** — Celery integration for long-running operations

### 🔧 Operations

- **A10 Device Pool Management** — Support for multiple A10 devices with load distribution
- **Configuration Backup/Restore** — Automated snapshots of A10 configurations
- **Dry-run Mode** — Preview changes before applying to production

### 🤖 AI/Automation

- **Incident Response Playbooks** — Pre-defined MCP workflows for common scenarios
- **Auto-mitigation Rules** — Trigger zone creation based on attack patterns
- **Natural Language Queries** — Ask questions about attacks and zones in plain English

Want to contribute? Open an issue or PR on [GitHub](https://github.com/opastorello/a10-guardian)!

## 📄 License

MIT

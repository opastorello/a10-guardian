# 🤖 MCP Integration Guide

Complete guide for integrating A10 Guardian with AI agents via **Model Context Protocol (MCP)**.

## 📋 Overview

The MCP server allows AI agents (Claude Desktop, n8n, or any MCP client) to interact directly with your A10 Thunder TPS devices through natural language commands. Agents can monitor system health, manage mitigation zones, configure templates, and respond to DDoS incidents—all through conversational interfaces.

## ✅ Prerequisites

- 🐍 Python 3.10+ installed
- 🛡️ Access to A10 Thunder TPS device
- 🔐 Credentials configured in `.env` file

## 🚀 Transport Modes

The MCP server supports two transport modes:

| Mode | Use Case | Default Port | Authentication |
|------|----------|--------------|----------------|
| **stdio** | Local clients (Claude Desktop) | — | Not required |
| **streamable-http** | Remote/network clients (n8n, Docker) | 8001 | Bearer token |

Set via `MCP_TRANSPORT` environment variable (default: `stdio`).

---

## 🖥️ Setup: Claude Desktop (stdio)

### Configuration File Location

- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Mac/Linux**: `~/Library/Application Support/Claude/claude_desktop_config.json`

### Configuration

Add the following entry under `mcpServers`:

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

### Using with `uv` (Alternative)

Replace the command with:

```json
{
  "command": "uv",
  "args": [
    "run",
    "--with", "fastmcp",
    "--with", "httpx",
    "--with", "pydantic-settings",
    "src/a10_guardian/mcp_server.py"
  ]
}
```

---

## 🌐 Setup: n8n / HTTP Clients (streamable-http)

### Option 1: Docker Compose

The MCP service is pre-configured on port 8001:

```bash
docker compose up -d
```

MCP endpoint: `http://localhost:8001/mcp`

### Option 2: Running Locally

```bash
MCP_TRANSPORT=streamable-http MCP_PORT=8001 python src/a10_guardian/mcp_server.py
```

### Connecting from n8n

Add an **MCP Client Tool** node with:

- **URL:** `http://<host>:8001/mcp`
- **Authentication:** Bearer Token
- **Token:** Your `API_SECRET_TOKEN` from `.env`

---

## 🔐 Authentication

| Transport | Authentication | Header |
|-----------|----------------|--------|
| **stdio** | None (local connection) | — |
| **streamable-http** | Bearer token required | `Authorization: Bearer <API_SECRET_TOKEN>` |

Requests without a valid token receive `401 Unauthorized`.

---

## 🛠️ Available Tools

The MCP server exposes 9 tools for AI agents:

### 🖥️ System & Monitoring

| Tool | Description | Example Usage |
|------|-------------|---------------|
| **`get_system_health()`** | Check if A10 device is online (hostname, uptime) | "What is the health status of the A10 system?" |
| **`list_active_mitigations()`** | List all IPs currently under mitigation | "Which IPs are being mitigated right now?" |
| **`get_zone_status(ip_address)`** | Full config and status of specific zone | "Show me the status of zone 203.0.113.5" |

### 🛡️ Mitigation Management

| Tool | Description | Example Usage |
|------|-------------|---------------|
| **`mitigate_ip(ip_address, template)`** | Create or re-sync mitigation using specified template | "Mitigate 203.0.113.5 using gaming template" |
| **`remove_mitigation(ip_address)`** | Stop mitigation and remove zone | "The attack stopped, remove mitigation for 203.0.113.5" |

### 📝 Template Management

| Tool | Description | Example Usage |
|------|-------------|---------------|
| **`list_zone_templates()`** | List all configured templates | "What templates are available?" |
| **`get_zone_template(name)`** | Retrieve template configuration | "Show me the gaming template" |
| **`set_zone_template(template_json, name)`** | Create/update template with A10 validation | "Create a new template called 'web-hosting'" |
| **`import_zone_template(ip_address, name)`** | Import template from existing A10 zone | "Import the config from 203.0.113.5 as template 'production'" |

---

## 📦 Resources

Resources provide data that AI agents can read as context.

| Resource URI | Description |
|--------------|-------------|
| `mitigation://zones/active` | Full JSON list of all active zones |

---

## 💡 Prompts

Prompts help AI agents execute complex tasks with pre-built context.

### `analyze_incident`

**Parameter:** `ip_address`

**What it does:**
1. Retrieves zone status for the specified IP
2. Collects global incident count
3. Identifies top attack types system-wide

**Example usage in chat:**

> "Analyze the incident on IP 203.0.113.50"

The agent will automatically use the prompt to gather all relevant context before providing a comprehensive incident analysis.

---

## 🔒 Security

- ✅ All MCP actions use credentials from `.env`
- ✅ HTTP mode requires valid Bearer token on every request
- ✅ Communication with A10 device over HTTPS
- ✅ Audit logs for write operations saved to `logs/mcp.log`
- ✅ Session caching to minimize authentication requests
- ✅ Automatic CSRF token handling for A10 API calls

---

## 🎯 Example Workflows

### Responding to DDoS Attack

**User:** "I'm seeing high traffic on 203.0.113.100, can you help?"

**Agent:**
1. Calls `get_zone_status("203.0.113.100")` to check current protection
2. If not protected, calls `mitigate_ip("203.0.113.100", "default")`
3. Confirms mitigation deployed and monitoring active

### Template Management

**User:** "Create a new template for web servers based on the config of 203.0.113.5"

**Agent:**
1. Calls `import_zone_template("203.0.113.5", "web-servers")`
2. Validates configuration against A10 device
3. Saves template to `config/zone_templates/web-servers.json`

### Incident Analysis

**User:** "Analyze the incident on 203.0.113.50"

**Agent:**
1. Triggers `analyze_incident` prompt
2. Gathers zone status, incident data, and attack patterns
3. Provides detailed analysis with recommendations

---

## 📊 Monitoring Integration

The MCP server integrates with the REST API's attack monitoring system:

- 🚨 **Real-time attack detection** across all zones
- 🔔 **Webhook notifications** to Slack/Discord
- 📈 **Attack statistics** and incident tracking
- ⏱️ **Duration tracking** for ongoing attacks

Agents can query attack status via:

```
"Are there any ongoing attacks?"
"Show me attack statistics for the last hour"
"What's the current threat level?"
```

---

## 🐛 Troubleshooting

### Connection Issues

**Problem:** Agent can't connect to MCP server

**Solution:**
- Verify `MCP_TRANSPORT` is set correctly
- Check port 8001 is accessible (HTTP mode)
- Confirm `.env` credentials are valid
- Review `logs/mcp.log` for error messages

### Authentication Failures

**Problem:** `401 Unauthorized` responses

**Solution:**
- Verify `Authorization: Bearer <token>` header is set
- Confirm `API_SECRET_TOKEN` matches `.env` value
- Check token doesn't have leading/trailing spaces

### Tool Execution Errors

**Problem:** Tools fail with A10 API errors

**Solution:**
- Verify A10 device is accessible at `A10_BASE_URL`
- Check credentials have sufficient permissions
- Review `logs/audit.log` for detailed error messages
- Confirm SSL certificate validation settings (`A10_VERIFY_SSL`)

---

## 📚 Additional Resources

- [Main README](../README.md) - Full project documentation
- [Template System](../config/zone_templates/README.md) - Template configuration guide
- [FastMCP Documentation](https://github.com/jlowin/fastmcp) - MCP framework details
- [Model Context Protocol Spec](https://modelcontextprotocol.io/) - Official MCP specification

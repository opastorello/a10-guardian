# A10 Guardian - Guia de Integração

## 🔗 API REST - Endpoint Base

```
Base URL: http://localhost:8000/api/v1
Token: plCQr3SiHOLOYbe0bwL8o9u8qINwvEsuJ5dnAVWM8L8pETMh7R0FXtK91AOBwKYN
Header: x-api-token
```

---

## 🔄 N8N - Automação de Workflows

### Configuração Inicial

1. **Criar Credencial HTTP Header Auth:**
   - Nome: `A10 Guardian API`
   - Header Name: `x-api-token`
   - Header Value: `plCQr3SiHOLOYbe0bwL8o9u8qINwvEsuJ5dnAVWM8L8pETMh7R0FXtK91AOBwKYN`

### Exemplos de Workflows

#### 1. Mitigação Automática de IP
```json
{
  "nodes": [
    {
      "name": "Webhook - Receber IP",
      "type": "n8n-nodes-base.webhook",
      "parameters": {
        "path": "mitigate-ip",
        "httpMethod": "POST"
      }
    },
    {
      "name": "A10 - Mitigar IP",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "method": "POST",
        "url": "http://localhost:8000/api/v1/mitigation/zones/mitigate/{{$json.body.ip}}?template=default",
        "authentication": "predefinedCredentialType",
        "nodeCredentialType": "httpHeaderAuth"
      }
    },
    {
      "name": "Notificar Slack",
      "type": "n8n-nodes-base.slack"
    }
  ]
}
```

#### 2. Monitoramento de Zonas a Cada 5 Minutos
```json
{
  "nodes": [
    {
      "name": "Cron - A cada 5min",
      "type": "n8n-nodes-base.cron",
      "parameters": {
        "triggerTimes": {
          "item": [{"mode": "everyX", "value": 5, "unit": "minutes"}]
        }
      }
    },
    {
      "name": "A10 - Listar Zonas",
      "type": "n8n-nodes-base.httpRequest",
      "parameters": {
        "url": "http://localhost:8000/api/v1/mitigation/zones/list"
      }
    },
    {
      "name": "Filtrar Modo Protect",
      "type": "n8n-nodes-base.filter",
      "parameters": {
        "conditions": {
          "string": [
            {"value1": "={{$json.operational_mode}}", "value2": "protect"}
          ]
        }
      }
    }
  ]
}
```

---

## 🤖 Claude API (Anthropic) - Function Calling

### Definição de Ferramentas

```python
import anthropic

client = anthropic.Anthropic(api_key="your-api-key")

tools = [
    {
        "name": "get_system_health",
        "description": "Get A10 Thunder TPS system health and status",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "list_active_mitigations",
        "description": "List all active DDoS mitigation zones",
        "input_schema": {
            "type": "object",
            "properties": {
                "page": {"type": "integer", "description": "Page number"},
                "items": {"type": "integer", "description": "Items per page"}
            }
        }
    },
    {
        "name": "mitigate_ip",
        "description": "Start DDoS mitigation for a specific IP address",
        "input_schema": {
            "type": "object",
            "properties": {
                "ip_address": {"type": "string", "description": "IP address to protect"},
                "template": {"type": "string", "description": "Template name (default: 'default')"}
            },
            "required": ["ip_address"]
        }
    },
    {
        "name": "remove_mitigation",
        "description": "Remove DDoS mitigation for an IP address",
        "input_schema": {
            "type": "object",
            "properties": {
                "ip_address": {"type": "string", "description": "IP address to unprotect"}
            },
            "required": ["ip_address"]
        }
    }
]

def execute_tool(tool_name: str, tool_input: dict) -> dict:
    """Execute A10 Guardian API call based on tool"""
    import httpx

    base_url = "http://localhost:8000/api/v1"
    headers = {"x-api-token": "plCQr3SiHOLOYbe0bwL8o9u8qINwvEsuJ5dnAVWM8L8pETMh7R0FXtK91AOBwKYN"}

    if tool_name == "get_system_health":
        response = httpx.get(f"{base_url}/system/info", headers=headers)
        return response.json()

    elif tool_name == "list_active_mitigations":
        page = tool_input.get("page", 1)
        items = tool_input.get("items", 10)
        response = httpx.get(f"{base_url}/mitigation/zones/list?page={page}&items={items}", headers=headers)
        return response.json()

    elif tool_name == "mitigate_ip":
        ip = tool_input["ip_address"]
        template = tool_input.get("template", "default")
        response = httpx.post(f"{base_url}/mitigation/zones/mitigate/{ip}?template={template}", headers=headers)
        return response.json()

    elif tool_name == "remove_mitigation":
        ip = tool_input["ip_address"]
        response = httpx.delete(f"{base_url}/mitigation/zones/remove/{ip}", headers=headers)
        return response.json()

# Usar com Claude
message = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    tools=tools,
    messages=[{"role": "user", "content": "Proteja o IP 192.0.2.100 contra DDoS"}]
)

# Processar tool calls
for content in message.content:
    if content.type == "tool_use":
        result = execute_tool(content.name, content.input)
        print(f"Tool: {content.name}")
        print(f"Result: {result}")
```

---

## 🧠 Google Gemini - Function Calling

```python
import google.generativeai as genai

genai.configure(api_key="your-api-key")

# Definir funções
mitigate_ip_declaration = {
    "name": "mitigate_ip",
    "description": "Start DDoS mitigation for an IP address",
    "parameters": {
        "type": "object",
        "properties": {
            "ip_address": {
                "type": "string",
                "description": "IP address to protect"
            },
            "template": {
                "type": "string",
                "description": "Template name",
                "enum": ["default", "test_imported"]
            }
        },
        "required": ["ip_address"]
    }
}

list_zones_declaration = {
    "name": "list_active_mitigations",
    "description": "List all active DDoS mitigation zones",
    "parameters": {
        "type": "object",
        "properties": {}
    }
}

# Criar modelo com funções
model = genai.GenerativeModel(
    model_name="gemini-1.5-pro",
    tools=[mitigate_ip_declaration, list_zones_declaration]
)

# Chat com function calling
chat = model.start_chat()
response = chat.send_message("Preciso proteger o IP 203.0.113.50")

# Processar function calls
for part in response.parts:
    if fn := part.function_call:
        if fn.name == "mitigate_ip":
            import httpx
            result = httpx.post(
                f"http://localhost:8000/api/v1/mitigation/zones/mitigate/{fn.args['ip_address']}?template=default",
                headers={"x-api-token": "YOUR_TOKEN"}
            )
            print(result.json())
```

---

## 🔌 Make.com (Integromat)

### HTTP Request Module

**Configuração:**
```
URL: http://localhost:8000/api/v1/mitigation/zones/mitigate/{{IP}}?template=default
Method: POST
Headers:
  - x-api-token: plCQr3SiHOLOYbe0bwL8o9u8qINwvEsuJ5dnAVWM8L8pETMh7R0FXtK91AOBwKYN
```

---

## 🔗 Zapier

### Webhook Configuration

**URL:** `http://localhost:8000/api/v1/mitigation/zones/mitigate/{{ip}}?template=default`

**Headers:**
```json
{
  "x-api-token": "plCQr3SiHOLOYbe0bwL8o9u8qINwvEsuJ5dnAVWM8L8pETMh7R0FXtK91AOBwKYN"
}
```

---

## 📊 Power Automate (Microsoft)

### HTTP Action

```json
{
  "method": "POST",
  "uri": "http://localhost:8000/api/v1/mitigation/zones/mitigate/@{variables('IP')}?template=default",
  "headers": {
    "x-api-token": "plCQr3SiHOLOYbe0bwL8o9u8qINwvEsuJ5dnAVWM8L8pETMh7R0FXtK91AOBwKYN"
  }
}
```

---

## 🐍 Python - Wrapper Completo

```python
import httpx
from typing import Optional, Dict, Any

class A10Guardian:
    def __init__(self, base_url: str = "http://localhost:8000/api/v1",
                 api_token: str = "plCQr3SiHOLOYbe0bwL8o9u8qINwvEsuJ5dnAVWM8L8pETMh7R0FXtK91AOBwKYN"):
        self.base_url = base_url
        self.headers = {"x-api-token": api_token}

    def get_system_health(self) -> Dict[str, Any]:
        """Get A10 system health"""
        response = httpx.get(f"{self.base_url}/system/info", headers=self.headers)
        return response.json()

    def list_zones(self, page: int = 1, items: int = 50) -> Dict[str, Any]:
        """List all mitigation zones"""
        response = httpx.get(
            f"{self.base_url}/mitigation/zones/list?page={page}&items={items}",
            headers=self.headers
        )
        return response.json()

    def mitigate_ip(self, ip: str, template: str = "default") -> Dict[str, Any]:
        """Start mitigation for an IP"""
        response = httpx.post(
            f"{self.base_url}/mitigation/zones/mitigate/{ip}?template={template}",
            headers=self.headers,
            timeout=30
        )
        return response.json()

    def remove_mitigation(self, ip: str) -> Dict[str, Any]:
        """Remove mitigation for an IP"""
        response = httpx.delete(
            f"{self.base_url}/mitigation/zones/remove/{ip}",
            headers=self.headers,
            timeout=30
        )
        return response.json()

    def get_zone_status(self, ip: str) -> Dict[str, Any]:
        """Get status of a specific zone"""
        response = httpx.get(
            f"{self.base_url}/mitigation/zones/status/{ip}",
            headers=self.headers
        )
        return response.json()

# Uso
a10 = A10Guardian()
print(a10.get_system_health())
print(a10.mitigate_ip("192.0.2.100"))
```

---

## 🌐 Expor API Publicamente (Opcional)

Se quiser que N8N Cloud, Claude API, etc acessem de fora:

### 1. Usando Ngrok
```bash
ngrok http 8000
```

### 2. Usando Cloudflare Tunnel
```bash
cloudflared tunnel --url http://localhost:8000
```

### 3. Configurar Firewall
```bash
# Abrir porta 8000 (cuidado com segurança!)
# Certifique-se de usar HTTPS em produção
```

---

## 🔐 Segurança

**IMPORTANTE:** Em produção:

1. **Use HTTPS** (configure certificado SSL/TLS)
2. **Proteja o token** (use variáveis de ambiente)
3. **Configure firewall** (whitelist de IPs)
4. **Rate limiting** (já incluído: 60 req/min)
5. **Monitore logs** de acesso

---

## 📞 Suporte

- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
- Logs: `docker compose logs api -f`

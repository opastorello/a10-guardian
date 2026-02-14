# 📚 A10 Guardian - Documentação Completa

Documentação oficial da API A10 Guardian para gerenciamento de mitigação DDoS.

---

## 📖 Guias Disponíveis

### 🚀 [Guia de Uso da API](./API_USAGE.md)
Documentação completa da API REST com exemplos em Python e JavaScript.

**Conteúdo:**
- Endpoints da API REST
- Autenticação e tokens
- Exemplos de requisições
- Notificações automáticas
- Monitoramento e logs

### 🔗 [Guia de Integrações](./INTEGRATION_GUIDE.md)
Como integrar A10 Guardian com outras plataformas e ferramentas.

**Plataformas suportadas:**
- **N8N** - Automação de workflows
- **Claude API (Anthropic)** - Function calling para IA
- **Google Gemini** - Integrações com IA
- **Make.com** - Automação visual
- **Zapier** - Integrações cloud
- **Power Automate** - Microsoft
- **Python/JavaScript** - SDKs e wrappers

### ⚙️ [Configuração N8N](./N8N_INTEGRATION.json)
Arquivo JSON pronto para importar workflows no N8N.

**Workflows incluídos:**
- Get System Health
- List Zones
- Mitigate IP
- Remove Mitigation
- Receive Attack Alert (webhook)

### 🔧 [MCP Usage Guide](./MCP_USAGE.md)
Documentação do servidor MCP (Model Context Protocol).

---

## 🎯 Quick Start

### 1. Verificar Status da API

```bash
curl http://localhost:8000/health
```

### 2. Obter System Health

```bash
curl -X GET http://localhost:8000/api/v1/system/info \
  -H "x-api-token: SEU_TOKEN"
```

### 3. Listar Zonas Ativas

```bash
curl -X GET http://localhost:8000/api/v1/mitigation/zones/list \
  -H "x-api-token: SEU_TOKEN"
```

### 4. Mitigar um IP

```bash
curl -X POST http://localhost:8000/api/v1/mitigation/zones/mitigate/192.0.2.100?template=default \
  -H "x-api-token: SEU_TOKEN"
```

---

## 🔐 Autenticação

Todas as requisições requerem o header de autenticação:

```
x-api-token: plCQr3SiHOLOYbe0bwL8o9u8qINwvEsuJ5dnAVWM8L8pETMh7R0FXtK91AOBwKYN
```

---

## 📊 Endpoints Principais

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/api/v1/system/info` | Informações do sistema A10 |
| `GET` | `/api/v1/system/devices` | Lista dispositivos |
| `GET` | `/api/v1/system/license` | Informações de licença |
| `GET` | `/api/v1/mitigation/zones/list` | Lista zonas de mitigação |
| `POST` | `/api/v1/mitigation/zones/mitigate/{ip}` | Inicia mitigação |
| `DELETE` | `/api/v1/mitigation/zones/remove/{ip}` | Remove mitigação |
| `GET` | `/api/v1/mitigation/zones/status/{ip}` | Status de zona |
| `GET` | `/api/v1/templates/list` | Lista templates |

---

## 🔔 Notificações Automáticas

O sistema envia notificações para **Discord** e **Telegram** automaticamente:

### Eventos Notificados

**Zone Changes (Mudanças Externas):**
- ✨ Zone Created - Nova zona criada fora da API
- 🔧 Zone Modified - Zona modificada fora da API
- 🗑️ Zone Deleted - Zona removida fora da API
- 👤 Inclui nome do usuário responsável

**Attack Monitoring:**
- 🚨 Attack Detected - Ataque DDoS detectado
- ✅ Attack Mitigated - Ataque mitigado
- ⏱️ Attack Ongoing - Ataques em andamento

**Mitigation Operations:**
- 🛡️ Mitigation Started - Via API
- 🔓 Mitigation Stopped - Via API

**System Health:**
- 💚 Device Online
- 🔴 Device Offline

---

## 🐍 SDK Python

### Instalação
```bash
pip install httpx
```

### Exemplo de Uso
```python
import httpx

class A10Guardian:
    def __init__(self):
        self.base_url = "http://localhost:8000/api/v1"
        self.headers = {
            "x-api-token": "plCQr3SiHOLOYbe0bwL8o9u8qINwvEsuJ5dnAVWM8L8pETMh7R0FXtK91AOBwKYN"
        }

    def mitigate_ip(self, ip: str, template: str = "default"):
        response = httpx.post(
            f"{self.base_url}/mitigation/zones/mitigate/{ip}?template={template}",
            headers=self.headers,
            timeout=30
        )
        return response.json()

# Uso
a10 = A10Guardian()
result = a10.mitigate_ip("192.0.2.100")
print(result)
```

---

## 🌐 Expor API Publicamente

Para acessar a API de fora da rede local:

### Opção 1: Ngrok (Recomendado para testes)
```bash
ngrok http 8000
```

### Opção 2: Cloudflare Tunnel
```bash
cloudflared tunnel --url http://localhost:8000
```

⚠️ **Segurança:** Use HTTPS em produção e configure firewall adequadamente.

---

## 📦 Exemplos Práticos

### N8N Workflow - Auto Mitigation
1. Webhook recebe alerta de ataque
2. HTTP Request mitiga o IP automaticamente
3. Envia notificação para Slack

### Claude API - Assistente DDoS
```python
# Ver exemplo completo em ../test_claude_api.py
from anthropic import Anthropic

client = Anthropic(api_key="your-key")
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    tools=[...],  # Tools do A10 Guardian
    messages=[{"role": "user", "content": "Proteja o IP 192.0.2.100"}]
)
```

### Gemini Function Calling
Ver exemplos completos em [INTEGRATION_GUIDE.md](./INTEGRATION_GUIDE.md)

---

## 🛠️ Troubleshooting

### API não responde
```bash
# Verificar status do container
docker compose ps

# Verificar logs
docker compose logs api -f
```

### Token inválido
Verifique se está usando o header correto: `x-api-token`

### Timeout na criação de zona
Zonas podem levar 20-30 segundos para serem criadas. Aumentar timeout da requisição.

---

## 📞 Suporte

- **API Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health
- **Logs:** `docker compose logs api -f`
- **GitHub Issues:** [Reportar problema](https://github.com/seu-repo/issues)

---

## 🔄 Versão

**A10 Guardian v1.0.0**
- FastAPI + Python 3.10+
- A10 Networks Thunder TPS Integration
- MCP Server Support
- Multi-channel Notifications

---

## 📝 Licença

Ver arquivo LICENSE na raiz do projeto.

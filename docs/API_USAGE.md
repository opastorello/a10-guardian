# A10 Guardian - Guia de Uso da API

## API REST (Recomendado para uso direto)

Base URL: `http://localhost:8000/api/v1/`
Token: `plCQr3SiHOLOYbe0bwL8o9u8qINwvEsuJ5dnAVWM8L8pETMh7R0FXtK91AOBwKYN`

### Endpoints Disponíveis

#### 1. System Health
```bash
curl -X GET "http://localhost:8000/api/v1/system/info" \
  -H "x-api-token: plCQr3SiHOLOYbe0bwL8o9u8qINwvEsuJ5dnAVWM8L8pETMh7R0FXtK91AOBwKYN"
```

#### 2. Listar Mitigações Ativas
```bash
curl -X GET "http://localhost:8000/api/v1/mitigation/zones/list?page=1&items=10" \
  -H "x-api-token: plCQr3SiHOLOYbe0bwL8o9u8qINwvEsuJ5dnAVWM8L8pETMh7R0FXtK91AOBwKYN"
```

#### 3. Mitigar IP
```bash
curl -X POST "http://localhost:8000/api/v1/mitigation/zones/mitigate/38.3.165.23?template=default" \
  -H "x-api-token: plCQr3SiHOLOYbe0bwL8o9u8qINwvEsuJ5dnAVWM8L8pETMh7R0FXtK91AOBwKYN"
```

#### 4. Status de Zona
```bash
curl -X GET "http://localhost:8000/api/v1/mitigation/zones/status/38.3.165.23" \
  -H "x-api-token: plCQr3SiHOLOYbe0bwL8o9u8qINwvEsuJ5dnAVWM8L8pETMh7R0FXtK91AOBwKYN"
```

#### 5. Remover Mitigação
```bash
curl -X DELETE "http://localhost:8000/api/v1/mitigation/zones/remove/38.3.165.23" \
  -H "x-api-token: plCQr3SiHOLOYbe0bwL8o9u8qINwvEsuJ5dnAVWM8L8pETMh7R0FXtK91AOBwKYN"
```

#### 6. Listar Templates
```bash
curl -X GET "http://localhost:8000/api/v1/templates/list" \
  -H "x-api-token: plCQr3SiHOLOYbe0bwL8o9u8qINwvEsuJ5dnAVWM8L8pETMh7R0FXtK91AOBwKYN"
```

## Integração com Aplicações

### Python
```python
import httpx

API_URL = "http://localhost:8000/api/v1"
API_TOKEN = "plCQr3SiHOLOYbe0bwL8o9u8qINwvEsuJ5dnAVWM8L8pETMh7R0FXtK91AOBwKYN"

headers = {"x-api-token": API_TOKEN}

# Mitigar IP
response = httpx.post(
    f"{API_URL}/mitigation/zones/mitigate/192.0.2.100?template=default",
    headers=headers
)
print(response.json())

# Listar zonas
response = httpx.get(
    f"{API_URL}/mitigation/zones/list",
    headers=headers
)
print(response.json())
```

### JavaScript/Node.js
```javascript
const API_URL = "http://localhost:8000/api/v1";
const API_TOKEN = "plCQr3SiHOLOYbe0bwL8o9u8qINwvEsuJ5dnAVWM8L8pETMh7R0FXtK91AOBwKYN";

// Mitigar IP
fetch(`${API_URL}/mitigation/zones/mitigate/192.0.2.100?template=default`, {
  method: 'POST',
  headers: {
    'x-api-token': API_TOKEN
  }
})
.then(res => res.json())
.then(data => console.log(data));
```

## Notificações

O sistema envia notificações automaticamente para:
- **Discord**: Via webhook configurado
- **Telegram**: Bot token configurado

### Eventos que Geram Notificações

1. **Zone Changes (Mudanças Externas)**:
   - Zone Created (criada fora da API)
   - Zone Modified (modificada fora da API)
   - Zone Deleted (deletada fora da API)
   - Username do responsável incluído

2. **Attack Monitoring**:
   - Attack Detected (ataque detectado)
   - Attack Mitigated (ataque mitigado)
   - Attack Ongoing (atualizações de ataques longos)

3. **Mitigation Operations**:
   - Mitigation Started (via API)
   - Mitigation Stopped (via API)

4. **System Health**:
   - Device Online/Offline

## Monitoramento

### Logs
```bash
# API logs
docker compose logs api -f

# MCP logs
docker compose logs mcp -f

# Filtrar por tipo
docker compose logs api | grep "Zone"
docker compose logs api | grep "Attack"
```

### Status
```bash
# Container status
docker compose ps

# System health
curl http://localhost:8000/health
```

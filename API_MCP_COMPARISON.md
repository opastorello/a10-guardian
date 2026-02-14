# API REST vs MCP Tools - Comparação Completa

## 📊 Endpoints API REST Disponíveis

### 🖥️ System Endpoints
| Método | Endpoint | Descrição | MCP Tool? |
|--------|----------|-----------|-----------|
| GET | `/api/v1/system/info` | System information | ✅ `get_system_health` |
| GET | `/api/v1/system/devices` | List devices | ❌ **FALTANDO** |
| GET | `/api/v1/system/license` | License info | ❌ **FALTANDO** |

### 🛡️ Mitigation Endpoints
| Método | Endpoint | Descrição | MCP Tool? |
|--------|----------|-----------|-----------|
| POST | `/api/v1/mitigation/zones/mitigate/{ip}` | Start mitigation | ✅ `mitigate_ip` |
| GET | `/api/v1/mitigation/zones/list` | List zones | ✅ `list_active_mitigations` |
| GET | `/api/v1/mitigation/zones/status/{ip}` | Zone status | ✅ `get_zone_status` |
| DELETE | `/api/v1/mitigation/zones/remove/{ip}` | Remove zone | ✅ `remove_mitigation` |

### 📝 Template Endpoints
| Método | Endpoint | Descrição | MCP Tool? |
|--------|----------|-----------|-----------|
| GET | `/api/v1/templates/list` | List templates | ✅ `list_zone_templates` |
| GET | `/api/v1/templates/{name}` | Get template | ✅ `get_zone_template` |
| POST | `/api/v1/templates/{name}` | Save template | ✅ `set_zone_template` |
| DELETE | `/api/v1/templates/{name}` | Delete template | ❌ **FALTANDO** |
| GET | `/api/v1/templates/{name}/preview` | Preview template | ❌ **FALTANDO** |
| POST | `/api/v1/templates/{name}/export` | Export template | ❌ **FALTANDO** |
| POST | `/api/v1/templates/import/{ip}` | Import from zone | ✅ `import_zone_template` |

### ⚔️ Attack Monitoring Endpoints
| Método | Endpoint | Descrição | MCP Tool? |
|--------|----------|-----------|-----------|
| GET | `/api/v1/attacks/ongoing` | List ongoing attacks | ❌ **FALTANDO** |
| GET | `/api/v1/attacks/history` | Attack history | ❌ **FALTANDO** |
| GET | `/api/v1/attacks/{incident_id}/stats` | Attack stats | ❌ **FALTANDO** |

---

## 🔧 MCP Tools Atuais (9 tools)

1. ✅ `get_system_health` - System info
2. ✅ `list_active_mitigations` - List zones
3. ✅ `mitigate_ip` - Start mitigation
4. ✅ `get_zone_status` - Zone status
5. ✅ `remove_mitigation` - Remove zone
6. ✅ `get_zone_template` - Get template
7. ✅ `set_zone_template` - Save template
8. ✅ `list_zone_templates` - List templates
9. ✅ `import_zone_template` - Import template

---

## 🆕 MCP Tools Sugeridos (6 novos)

### 1. `get_system_devices`
Get list of A10 devices in the cluster
```python
@mcp.tool()
def get_system_devices() -> str:
    """List all A10 TPS devices in the deployment"""
```

### 2. `get_system_license`
Get A10 license information
```python
@mcp.tool()
def get_system_license() -> str:
    """Get A10 Thunder TPS license details"""
```

### 3. `list_ongoing_attacks`
List active DDoS attacks being mitigated
```python
@mcp.tool()
def list_ongoing_attacks() -> str:
    """List all ongoing DDoS attacks currently being mitigated"""
```

### 4. `get_attack_stats`
Get detailed statistics for a specific attack
```python
@mcp.tool()
def get_attack_stats(incident_id: str) -> str:
    """Get detailed statistics for a specific DDoS attack incident"""
```

### 5. `get_attack_history`
Get historical attack data
```python
@mcp.tool()
def get_attack_history(hours: int = 24) -> str:
    """Get DDoS attack history for the last N hours"""
```

### 6. `delete_template`
Delete a zone template
```python
@mcp.tool()
def delete_template(name: str) -> str:
    """Delete a zone template configuration"""
```

---

## 📈 Comparação de Cobertura

| Categoria | Endpoints REST | MCP Tools | Cobertura |
|-----------|----------------|-----------|-----------|
| **System** | 3 | 1 | 33% |
| **Mitigation** | 4 | 4 | 100% ✅ |
| **Templates** | 7 | 4 | 57% |
| **Attacks** | 3 | 0 | 0% ⚠️ |
| **TOTAL** | **17** | **9** | **53%** |

---

## 🎯 Recomendação

### Prioridade Alta (adicionar agora):
1. ✅ `list_ongoing_attacks` - Essencial para monitoramento
2. ✅ `get_system_devices` - Info importante do cluster
3. ✅ `get_system_license` - Verificação de licença

### Prioridade Média (adicionar depois):
4. `get_attack_stats` - Detalhes de ataques
5. `get_attack_history` - Histórico
6. `delete_template` - Gerenciamento de templates

---

## 💡 Implementação

Vou implementar os 3 tools prioritários:
- `list_ongoing_attacks`
- `get_system_devices`
- `get_system_license`

Isso levará a cobertura de **53% → 71%**

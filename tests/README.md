# 🧪 A10 Guardian - Testes

Suite completa de testes para o A10 Guardian.

---

## 📁 Estrutura de Testes

```
tests/
├── test_api_endpoints.py          # Testes dos endpoints REST
├── test_auth_service.py            # Testes de autenticação A10
├── test_client.py                  # Testes do cliente HTTP
├── test_mitigation_service.py      # Testes do serviço de mitigação
├── test_notification_service.py    # Testes de notificações
├── test_system_service.py          # Testes do serviço de sistema
├── test_health.py                  # Teste de health check
├── test_mcp_integration.py         # Testes de integração MCP
├── test_mcp.py                     # Testes do servidor MCP
├── test_mcp_simple.py              # Testes simples de saúde MCP
├── test_claude_api.py              # Exemplo de integração Claude API
└── verify_mcp_runtime.py           # Verificação de runtime MCP

integration/                        # Testes de integração
performance/                        # Testes de performance
```

---

## 🚀 Executar Testes

### Todos os Testes
```bash
pytest tests/ -v
```

### Testes Específicos
```bash
# API endpoints
pytest tests/test_api_endpoints.py -v

# Authentication
pytest tests/test_auth_service.py -v

# Notifications
pytest tests/test_notification_service.py -v

# MCP integration
pytest tests/test_mcp_integration.py -v
```

### Com Cobertura
```bash
pytest tests/ --cov=src/a10_guardian --cov-report=html
```

---

## 🔧 Testes Manuais

### 1. Teste MCP Server Health
```bash
python tests/test_mcp_simple.py
```

**Saída esperada:**
```
[OK] MCP Server is running
[OK] Port 8001 is listening
[OK] MCP endpoint is protected
```

### 2. Teste MCP Completo
```bash
python tests/test_mcp.py
```

**Saída esperada:**
```
Root Endpoint        [OK] PASS
MCP Initialize       [OK] PASS
MCP List Tools       [FAIL] FAIL  # Expected - requires SSE client
```

### 3. Teste Claude API Integration
```bash
# Sem Claude API (demo local)
python tests/test_claude_api.py

# Com Claude API (requer ANTHROPIC_API_KEY)
export ANTHROPIC_API_KEY=your-key
python tests/test_claude_api.py
```

---

## 🧪 Tipos de Testes

### Unit Tests (pytest)
Testes unitários dos serviços e componentes principais.

**Executar:**
```bash
pytest tests/test_*.py -v
```

### Integration Tests
Testes de integração com A10 device real ou mock.

**Executar:**
```bash
pytest tests/integration/ -v
```

### Performance Tests
Testes de carga e performance da API.

**Executar:**
```bash
pytest tests/performance/ -v
```

### Manual Tests
Scripts Python para testes manuais e debugging.

**Executar:**
```bash
python tests/test_mcp_simple.py
python tests/test_claude_api.py
```

---

## 🔍 Testes por Componente

### API REST
- `test_api_endpoints.py` - Endpoints HTTP
- `test_health.py` - Health check

### Serviços
- `test_auth_service.py` - Autenticação A10
- `test_mitigation_service.py` - Mitigação DDoS
- `test_notification_service.py` - Notificações
- `test_system_service.py` - System info

### MCP Server
- `test_mcp.py` - Servidor MCP
- `test_mcp_simple.py` - Health check MCP
- `test_mcp_integration.py` - Integração MCP

### Integrações
- `test_claude_api.py` - Claude API function calling

---

## 📊 Cobertura de Testes

Objetivo: **>80% de cobertura**

```bash
# Gerar relatório de cobertura
pytest tests/ --cov=src/a10_guardian --cov-report=html

# Ver relatório
# Abrir: htmlcov/index.html
```

---

## 🐛 Debugging

### Logs Detalhados
```bash
pytest tests/ -v -s --log-cli-level=DEBUG
```

### Testar Apenas Falhas Anteriores
```bash
pytest tests/ --lf
```

### Parar no Primeiro Erro
```bash
pytest tests/ -x
```

### Executar Teste Específico
```bash
pytest tests/test_api_endpoints.py::test_get_system_info -v
```

---

## 🔐 Variáveis de Ambiente para Testes

```bash
# A10 Device (para testes de integração)
export A10_USERNAME=admin
export A10_PASSWORD=password
export A10_BASE_URL=https://a10-device:17489
export API_SECRET_TOKEN=test-token

# Claude API (para test_claude_api.py)
export ANTHROPIC_API_KEY=your-api-key

# Gemini API
export GOOGLE_API_KEY=your-api-key
```

---

## ✅ Checklist de Testes

Antes de fazer deploy:

- [ ] Todos os testes unitários passam (`pytest tests/`)
- [ ] Cobertura >80% (`pytest --cov`)
- [ ] Testes de integração passam (`pytest tests/integration/`)
- [ ] Health check funciona (`python tests/test_mcp_simple.py`)
- [ ] API REST acessível (`curl http://localhost:8000/health`)
- [ ] MCP server responde (`curl http://localhost:8001/`)
- [ ] Notificações funcionam (Discord/Telegram)
- [ ] Logs sem erros críticos

---

## 📝 Adicionar Novos Testes

### Template de Teste Unitário
```python
import pytest
from a10_guardian.services.seu_servico import SeuServico

def test_seu_servico():
    """Teste do seu serviço"""
    service = SeuServico()
    result = service.metodo()
    assert result == expected_value

def test_seu_servico_error():
    """Teste de erro do seu serviço"""
    service = SeuServico()
    with pytest.raises(ValueError):
        service.metodo_invalido()
```

### Template de Teste de Integração
```python
import httpx
import pytest

@pytest.mark.integration
def test_api_endpoint():
    """Teste de integração da API"""
    response = httpx.get("http://localhost:8000/api/v1/system/info")
    assert response.status_code == 200
    assert "hostname" in response.json()
```

---

## 🚨 CI/CD

### GitHub Actions
```yaml
# .github/workflows/tests.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run tests
        run: |
          pip install -e .[dev]
          pytest tests/ --cov --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

---

## 📞 Suporte

- **Documentação:** [../docs/README.md](../docs/README.md)
- **API Docs:** http://localhost:8000/docs
- **Issues:** GitHub Issues

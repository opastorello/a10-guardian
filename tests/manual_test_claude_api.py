#!/usr/bin/env python3
"""
Exemplo de integração do A10 Guardian com Claude API (Anthropic)
Demonstra function calling para automação de mitigação DDoS
"""

from typing import Any

import httpx

# Configuração da API A10 Guardian
A10_BASE_URL = "http://localhost:8000/api/v1"
A10_API_TOKEN = "plCQr3SiHOLOYbe0bwL8o9u8qINwvEsuJ5dnAVWM8L8pETMh7R0FXtK91AOBwKYN"

# Definição das ferramentas para Claude
TOOLS = [
    {
        "name": "get_system_health",
        "description": "Obtém informações de saúde e status do dispositivo A10 Thunder TPS DDoS mitigation",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "list_active_mitigations",
        "description": "Lista todas as zonas de mitigação DDoS ativas no A10",
        "input_schema": {
            "type": "object",
            "properties": {
                "page": {"type": "integer", "description": "Número da página (padrão: 1)"},
                "items": {"type": "integer", "description": "Itens por página (padrão: 10)"},
            },
        },
    },
    {
        "name": "mitigate_ip",
        "description": "Inicia mitigação DDoS para um endereço IP específico",
        "input_schema": {
            "type": "object",
            "properties": {
                "ip_address": {"type": "string", "description": "Endereço IP para proteger (ex: 192.0.2.100)"},
                "template": {"type": "string", "description": "Nome do template a usar (padrão: 'default')"},
            },
            "required": ["ip_address"],
        },
    },
    {
        "name": "get_zone_status",
        "description": "Obtém status detalhado de uma zona de mitigação específica",
        "input_schema": {
            "type": "object",
            "properties": {"ip_address": {"type": "string", "description": "Endereço IP da zona"}},
            "required": ["ip_address"],
        },
    },
    {
        "name": "remove_mitigation",
        "description": "Remove mitigação DDoS de um endereço IP",
        "input_schema": {
            "type": "object",
            "properties": {"ip_address": {"type": "string", "description": "Endereço IP para desproteger"}},
            "required": ["ip_address"],
        },
    },
]


def execute_tool(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    """
    Executa uma chamada à API do A10 Guardian baseada no tool escolhido
    """
    headers = {"x-api-token": A10_API_TOKEN}

    try:
        if tool_name == "get_system_health":
            response = httpx.get(f"{A10_BASE_URL}/system/info", headers=headers, timeout=10)
            return {"success": True, "data": response.json()}

        elif tool_name == "list_active_mitigations":
            page = tool_input.get("page", 1)
            items = tool_input.get("items", 10)
            response = httpx.get(
                f"{A10_BASE_URL}/mitigation/zones/list?page={page}&items={items}", headers=headers, timeout=10
            )
            return {"success": True, "data": response.json()}

        elif tool_name == "mitigate_ip":
            ip = tool_input["ip_address"]
            template = tool_input.get("template", "default")
            response = httpx.post(
                f"{A10_BASE_URL}/mitigation/zones/mitigate/{ip}?template={template}", headers=headers, timeout=30
            )
            return {"success": True, "data": response.json()}

        elif tool_name == "get_zone_status":
            ip = tool_input["ip_address"]
            response = httpx.get(f"{A10_BASE_URL}/mitigation/zones/status/{ip}", headers=headers, timeout=10)
            return {"success": True, "data": response.json()}

        elif tool_name == "remove_mitigation":
            ip = tool_input["ip_address"]
            response = httpx.delete(f"{A10_BASE_URL}/mitigation/zones/remove/{ip}", headers=headers, timeout=30)
            return {"success": True, "data": response.json()}

        else:
            return {"success": False, "error": f"Tool desconhecido: {tool_name}"}

    except Exception as e:
        return {"success": False, "error": str(e)}


def demo_without_claude():
    """
    Demonstração SEM Claude API - apenas testa as funções diretamente
    """
    print("=" * 70)
    print("Demo: A10 Guardian Function Calling (SEM Claude API)")
    print("=" * 70)

    # Teste 1: System Health
    print("\n[1] Get System Health")
    result = execute_tool("get_system_health", {})
    print(f"Result: {result}")

    # Teste 2: List Zones
    print("\n[2] List Active Mitigations")
    result = execute_tool("list_active_mitigations", {"page": 1, "items": 5})
    if result["success"]:
        zones = result["data"]
        print(f"Total zones: {zones.get('total', 0)}")
        for zone in zones.get("zones", [])[:3]:
            print(f"  - {zone['zone_name']} ({zone['operational_mode']})")

    # Teste 3: Get Zone Status
    print("\n[3] Get Zone Status (primeira zona)")
    if zones.get("zones"):
        first_zone_ip = zones["zones"][0]["zone_name"].split("-")[0]
        result = execute_tool("get_zone_status", {"ip_address": first_zone_ip})
        print(f"Result: {result}")

    print("\n" + "=" * 70)
    print("Demo concluída!")
    print("\nPara usar com Claude API:")
    print("1. Instale: pip install anthropic")
    print("2. Configure: export ANTHROPIC_API_KEY=your-key")
    print("3. Descomente a função demo_with_claude() abaixo")
    print("=" * 70)


def demo_with_claude():
    """
    Demonstração COM Claude API - requer anthropic package e API key
    Descomente esta função e instale: pip install anthropic
    """
    try:
        import os

        import anthropic

        # Verificar API key
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("ERRO: Configure ANTHROPIC_API_KEY no ambiente")
            return

        client = anthropic.Anthropic(api_key=api_key)

        print("=" * 70)
        print("Demo: A10 Guardian com Claude API")
        print("=" * 70)

        # Exemplo de pergunta ao Claude
        user_message = "Preciso proteger o IP 192.0.2.150 contra ataques DDoS"

        print(f"\nUser: {user_message}")

        # Fazer request ao Claude com tools
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            tools=TOOLS,
            messages=[{"role": "user", "content": user_message}],
        )

        print("\nClaude response:")
        print(f"Stop reason: {response.stop_reason}")

        # Processar tool calls
        if response.stop_reason == "tool_use":
            for content in response.content:
                if content.type == "tool_use":
                    print(f"\n[Tool Call] {content.name}")
                    print(f"Input: {content.input}")

                    # Executar tool
                    result = execute_tool(content.name, content.input)
                    print(f"Result: {result}")

        print("\n" + "=" * 70)

    except ImportError:
        print("ERRO: Pacote 'anthropic' não encontrado")
        print("Instale com: pip install anthropic")
    except Exception as e:
        print(f"ERRO: {e}")


if __name__ == "__main__":
    # Executar demo básica (funciona sempre)
    demo_without_claude()

    # Descomente abaixo para testar com Claude API (requer setup)
    # demo_with_claude()

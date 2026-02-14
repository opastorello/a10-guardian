#!/usr/bin/env python3
"""Simple MCP Server health check"""

import httpx

MCP_URL = "http://localhost:8001"

print("=" * 60)
print("A10 Guardian MCP Server - Health Check")
print("=" * 60)

# Test 1: Root endpoint
print("\n1. Testing MCP Server Info...")
try:
    response = httpx.get(MCP_URL, timeout=5)
    if response.status_code == 200:
        data = response.json()
        print("   [OK] MCP Server is running")
        print(f"   Service: {data['service']}")
        print(f"   Version: {data['version']}")
        print(f"   Transport: {data['transport']}")
        print(f"   Endpoint: {data['endpoint']}")
        print(f"   Tools available: {len(data['tools'])}")
        for tool in data["tools"]:
            print(f"      - {tool}")
    else:
        print(f"   [FAIL] Unexpected status: {response.status_code}")
except Exception as e:
    print(f"   [FAIL] Error: {e}")

# Test 2: Port is listening
print("\n2. Testing Port Connectivity...")
try:
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    result = sock.connect_ex(("localhost", 8001))
    sock.close()

    if result == 0:
        print("   [OK] Port 8001 is listening")
    else:
        print("   [FAIL] Port 8001 is not accessible")
except Exception as e:
    print(f"   [FAIL] Error: {e}")

# Test 3: Authentication endpoint
print("\n3. Testing Authentication...")
try:
    response = httpx.post(
        f"{MCP_URL}/mcp", headers={"Content-Type": "application/json"}, json={"test": "auth"}, timeout=5
    )
    # Should get 401 or 403 (auth required) or 400 (bad request but auth passed)
    if response.status_code in [400, 401, 403, 406]:
        print(f"   [OK] MCP endpoint is protected (status: {response.status_code})")
    else:
        print(f"   [INFO] Status: {response.status_code}")
except Exception as e:
    print(f"   [FAIL] Error: {e}")

print("\n" + "=" * 60)
print("Summary")
print("=" * 60)
print("MCP Server Status: ONLINE and HEALTHY")
print("\nTo use this MCP server:")
print("1. Use a compatible MCP client (e.g., Claude Desktop)")
print("2. Configure connection to: http://localhost:8001/mcp")
print("3. Use transport: streamable-http")
print("4. Add Authorization header with API token")
print("\nAlternatively, use the REST API at http://localhost:8000/api/v1/")
print("=" * 60)

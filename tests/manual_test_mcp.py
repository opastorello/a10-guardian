#!/usr/bin/env python3
"""Test MCP Server connectivity and tools"""

import json
import uuid

import httpx

MCP_URL = "http://localhost:8001"
API_TOKEN = "plCQr3SiHOLOYbe0bwL8o9u8qINwvEsuJ5dnAVWM8L8pETMh7R0FXtK91AOBwKYN"
SESSION_ID = str(uuid.uuid4())


def test_root():
    """Test root endpoint"""
    print("Testing root endpoint...")
    try:
        response = httpx.get(MCP_URL)
        print(f"[OK] Root endpoint: {response.status_code}")
        print(json.dumps(response.json(), indent=2))
        return True
    except Exception as e:
        print(f"[FAIL] Root endpoint failed: {e}")
        return False


def test_mcp_initialize():
    """Test MCP initialize"""
    print("\nTesting MCP initialize...")
    print(f"Session ID: {SESSION_ID}")
    try:
        headers = {
            "Authorization": f"Bearer {API_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "mcp-session-id": SESSION_ID,
        }

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }

        response = httpx.post(f"{MCP_URL}/mcp", headers=headers, json=payload, timeout=10)

        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}")

        if response.status_code == 200:
            print("[OK] MCP initialized successfully")
            return True
        else:
            print(f"[FAIL] MCP initialize failed: {response.status_code}")
            return False

    except Exception as e:
        print(f"[FAIL] MCP initialize error: {e}")
        return False


def test_mcp_list_tools():
    """Test MCP tools/list"""
    print("\nTesting MCP tools/list...")
    try:
        headers = {
            "Authorization": f"Bearer {API_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "mcp-session-id": SESSION_ID,
        }

        payload = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

        response = httpx.post(f"{MCP_URL}/mcp", headers=headers, json=payload, timeout=10)

        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"[OK] Found tools: {json.dumps(data, indent=2)[:300]}...")
            return True
        else:
            print(f"Response: {response.text[:300]}")
            print(f"[FAIL] List tools failed: {response.status_code}")
            return False

    except Exception as e:
        print(f"[FAIL] List tools error: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("A10 Guardian MCP Server Test")
    print("=" * 60)

    results = []
    results.append(("Root Endpoint", test_root()))
    results.append(("MCP Initialize", test_mcp_initialize()))
    results.append(("MCP List Tools", test_mcp_list_tools()))

    print("\n" + "=" * 60)
    print("Test Results:")
    print("=" * 60)
    for name, passed in results:
        status = "[OK] PASS" if passed else "[FAIL] FAIL"
        print(f"{name:20} {status}")

    total_passed = sum(1 for _, passed in results if passed)
    print(f"\nTotal: {total_passed}/{len(results)} tests passed")

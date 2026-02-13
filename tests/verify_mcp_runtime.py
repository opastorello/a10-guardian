import json
import os
import subprocess
import sys


def test_mcp_server():
    server_script = os.path.join("src", "a10_guardian", "mcp_server.py")
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")

    print(f"Starting MCP Server: {server_script}")

    process = subprocess.Popen(
        [sys.executable, server_script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
        text=True,
        env=env,
        bufsize=0,
    )

    try:
        # 1. Initialize
        print("[>] Sending 'initialize'...")
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        }
        process.stdin.write(json.dumps(init_req) + "\n")
        process.stdin.flush()

        resp_line = process.stdout.readline()
        print(f"[<] Received: {resp_line.strip()}")

        # 2. Initialized
        print("[>] Sending 'notifications/initialized'...")
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}) + "\n")
        process.stdin.flush()

        # 3. List Tools
        print("[>] Sending 'tools/list'...")
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}) + "\n")
        process.stdin.flush()

        resp_line = process.stdout.readline()
        while "notifications/message" in resp_line:
            print(f"[<] Log: {resp_line.strip()}")
            resp_line = process.stdout.readline()

        print(f"[<] Received: {resp_line.strip()}")

        data = json.loads(resp_line)
        if "result" in data:
            tools = data["result"]["tools"]
            print(f"[SUCCESS] Found {len(tools)} tools:")
            for t in tools:
                print(f" - {t['name']}")
        else:
            print("Failed to list tools.")

    except Exception as e:
        print(f"[!] Error: {e}")
    finally:
        process.terminate()


if __name__ == "__main__":
    test_mcp_server()

"""Manual smoke test for the 3 new MCP IP-management tools.

Hits the streamable-http MCP server on http://127.0.0.1:8001/mcp and exercises
zone_has_ip / add_ip_to_zone / remove_ip_from_zone against the real A10. Uses
192.0.2.99 (RFC 5737) as the test IP and the "On-Demand" zone.

Run while the MCP server is up:
    MCP_TRANSPORT=streamable-http MCP_PORT=8001 python src/a10_guardian/mcp_server.py
"""

import asyncio
import os
import sys

from fastmcp import Client
from fastmcp.client.auth import BearerAuth
from fastmcp.client.transports import StreamableHttpTransport

URL = os.environ.get("MCP_URL", "http://127.0.0.1:8001/mcp")
TOKEN = os.environ["MCP_SECRET_TOKEN"]
ZONE = "On-Demand"
IP = "192.0.2.99"


async def call(client, name, args):
    result = await client.call_tool(name, args)
    text = "".join(getattr(b, "text", "") for b in result.content)
    return text.strip()


async def main():
    transport = StreamableHttpTransport(URL, auth=BearerAuth(TOKEN))
    async with Client(transport) as client:
        print(f"=== zone_has_ip(zone={ZONE}, ip={IP}) — expect NOT present ===")
        print(await call(client, "zone_has_ip", {"zone_name": ZONE, "ip": IP}))

        print(f"\n=== add_ip_to_zone(zone={ZONE}, ip={IP}) — expect added ===")
        print(await call(client, "add_ip_to_zone", {"zone_name": ZONE, "ip": IP}))

        print(f"\n=== zone_has_ip — expect PRESENT ===")
        print(await call(client, "zone_has_ip", {"zone_name": ZONE, "ip": IP}))

        print(f"\n=== add_ip_to_zone again — expect already present (no change) ===")
        print(await call(client, "add_ip_to_zone", {"zone_name": ZONE, "ip": IP}))

        print(f"\n=== remove_ip_from_zone — expect removed ===")
        print(await call(client, "remove_ip_from_zone", {"zone_name": ZONE, "ip": IP}))

        print(f"\n=== zone_has_ip — expect NOT present ===")
        print(await call(client, "zone_has_ip", {"zone_name": ZONE, "ip": IP}))

        print(f"\n=== remove_ip_from_zone again — expect error (404 IP not present) ===")
        print(await call(client, "remove_ip_from_zone", {"zone_name": ZONE, "ip": IP}))


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

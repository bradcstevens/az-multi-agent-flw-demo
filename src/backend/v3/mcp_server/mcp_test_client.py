import asyncio
from fastmcp import Client

client = Client("mcp_server.py")


async def call_tool(name: str):
    async with client:
        result = await client.call_tool(
            "send_welcome_email",
            {"employee_name": name, "email_address": f"{name.lower()}@example.com"},
        )
        print(result)


asyncio.run(call_tool("Ford"))

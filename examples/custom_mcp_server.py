"""Example Custom MCP Server - Demonstrates how to create your own MCP server"""

import asyncio
import logging
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the MCP server instance
app = Server("custom-example-server")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    return [
        Tool(
            name="greet_user",
            description="Greets a user by name with a friendly message",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "The name of the person to greet",
                    },
                    "language": {
                        "type": "string",
                        "description": "Language for the greeting (english, spanish, french)",
                        "enum": ["english", "spanish", "french"],
                    },
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="calculate",
            description="Performs basic mathematical calculations",
            inputSchema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "description": "Mathematical operation to perform",
                        "enum": ["add", "subtract", "multiply", "divide"],
                    },
                    "a": {"type": "number", "description": "First number"},
                    "b": {"type": "number", "description": "Second number"},
                },
                "required": ["operation", "a", "b"],
            },
        ),
        Tool(
            name="get_time_info",
            description="Gets information about the current time",
            inputSchema={
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "Timezone (default: UTC)",
                    }
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool execution"""

    if name == "greet_user":
        user_name = arguments.get("name", "Friend")
        language = arguments.get("language", "english").lower()

        greetings = {
            "english": f"Hello, {user_name}! 👋 Welcome!",
            "spanish": f"¡Hola, {user_name}! 👋 ¡Bienvenido!",
            "french": f"Bonjour, {user_name}! 👋 Bienvenue!",
        }

        greeting = greetings.get(language, greetings["english"])

        return [TextContent(type="text", text=greeting)]

    elif name == "calculate":
        operation = arguments.get("operation")
        a = float(arguments.get("a", 0))
        b = float(arguments.get("b", 0))

        operations = {
            "add": a + b,
            "subtract": a - b,
            "multiply": a * b,
            "divide": a / b if b != 0 else "Error: Division by zero",
        }

        result = operations.get(operation, "Unknown operation")

        return [
            TextContent(type="text", text=f"Result: {a} {operation} {b} = {result}")
        ]

    elif name == "get_time_info":
        from datetime import datetime
        import pytz

        timezone = arguments.get("timezone", "UTC")

        try:
            tz = pytz.timezone(timezone)
            current_time = datetime.now(tz)

            info = f"""
Current Time Information:
- Timezone: {timezone}
- Date: {current_time.strftime("%Y-%m-%d")}
- Time: {current_time.strftime("%H:%M:%S")}
- Day of Week: {current_time.strftime("%A")}
"""

            return [TextContent(type="text", text=info.strip())]
        except Exception as e:
            return [TextContent(type="text", text=f"Error: {str(e)}")]

    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run the MCP server"""
    logger.info("Starting Custom Example MCP Server")

    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

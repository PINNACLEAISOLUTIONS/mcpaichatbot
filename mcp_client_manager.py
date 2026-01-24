"""MCP Client Manager - Handles connections to MCP servers and tool discovery"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.sse import sse_client
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MCPClientManager:
    """Manages connections to multiple MCP servers and their tools"""

    config: Dict[str, Any]
    clients: Dict[str, ClientSession]
    tools: Dict[str, List[Dict[str, Any]]]
    all_tools: List[Dict[str, Any]]

    def __init__(self, config_path: str = "mcp_config.json"):
        """
        Initialize the MCP Client Manager

        Args:
            config_path: Path to the MCP configuration JSON file
        """
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self.clients: Dict[str, ClientSession] = {}
        self.tools: Dict[str, List[Dict[str, Any]]] = {}
        self.all_tools: List[Dict[str, Any]] = []

    async def load_config(self) -> None:
        """Load MCP server configuration from JSON file"""
        try:
            with open(self.config_path, "r") as f:
                self.config = json.load(f)
            logger.info(f"Loaded MCP configuration from {self.config_path}")
            logger.info(
                f"Found {len(self.config.get('mcpServers', {}))} MCP servers configured"
            )
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {self.config_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in configuration file: {e}")
            raise

    async def connect_to_servers(self) -> None:
        """Connect to all configured MCP servers"""
        servers = self.config.get("mcpServers", {})

        for server_name, server_config in servers.items():
            try:
                await self._connect_server(server_name, server_config)
            except Exception as e:
                logger.error(f"Failed to connect to MCP server '{server_name}': {e}")
                # Continue with other servers even if one fails
                continue

    async def _connect_server(
        self, server_name: str, server_config: Dict[str, Any]
    ) -> None:
        """
        Connect to a single MCP server

        Args:
            server_name: Name of the server
            server_config: Server configuration dictionary
        """
        transport_type = server_config.get("type", "stdio")
        logger.info(f"Connecting to MCP server: {server_name} (type: {transport_type})")

        from contextlib import AsyncExitStack

        if not hasattr(self, "exit_stack"):
            self.exit_stack = AsyncExitStack()

        try:
            if transport_type == "stdio":
                command = server_config.get("command")
                raw_args = server_config.get("args", [])
                env_config = server_config.get("env", {})
                env = dict(os.environ)
                env.update(env_config)

                if not command:
                    logger.error(
                        f"No command specified for stdio server '{server_name}'"
                    )
                    return

                # Resolve paths in args relative to config file directory
                # This allows portable configs (deployment friendly)
                args = []
                config_dir = self.config_path.parent.resolve()

                for arg in raw_args:
                    # Check if arg looks like a relative path to a python script or directory
                    if isinstance(arg, str):
                        # Handle explicit relative paths ./ or %PROJECT_ROOT%
                        if arg.startswith("./") or arg.startswith("%PROJECT_ROOT%"):
                            clean_arg = arg.replace("%PROJECT_ROOT%", "").lstrip("./\\")
                            resolved_path = (config_dir / clean_arg).resolve()
                            args.append(str(resolved_path))
                        # Heuristic: if it ends with .py and exists relative to config, resolve it
                        elif arg.endswith(".py") and (config_dir / arg).exists():
                            args.append(str((config_dir / arg).resolve()))
                        else:
                            args.append(arg)
                    else:
                        args.append(arg)

                server_params = StdioServerParameters(
                    command=command, args=args, env=env if env else None
                )

                # Diagnostic: check if the first arg (often the script) exists
                if args and (args[0].endswith(".js") or args[0].endswith(".py")):
                    script_path = Path(args[0])
                    if not script_path.exists():
                        logger.error(
                            f"MCP Server '{server_name}' entry point NOT FOUND: {script_path.absolute()}"
                        )
                    else:
                        logger.info(
                            f"MCP Server '{server_name}' entry point verified: {script_path.absolute()}"
                        )

                logger.info(
                    f"Starting stdio server '{server_name}': {command} {' '.join(args)}"
                )
                stdio_transport = await self.exit_stack.enter_async_context(
                    stdio_client(server_params)
                )
                read_stream, write_stream = stdio_transport

            elif transport_type == "sse":
                url = server_config.get("url")
                if not url:
                    logger.error(f"No URL specified for SSE server '{server_name}'")
                    return

                # Connect via SSE
                logger.info(f"Attempting SSE connection to: {url}")
                sse_transport = await self.exit_stack.enter_async_context(
                    sse_client(url)
                )
                read_stream, write_stream = sse_transport
                logger.info(f"SSE transport established for {server_name}")

            else:
                logger.error(f"Unknown transport type: {transport_type}")
                return

            # Create and initialize the client session
            session = await self.exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await session.initialize()

            # Store the session for long-term use
            self.clients[server_name] = session

            # Discover tools from this server
            await self._discover_tools(server_name, session)

            logger.info(f"Successfully connected to MCP server: {server_name}")
        except Exception as e:
            logger.error(f"Failed to connect to server {server_name}: {e}")
            raise

    async def _discover_tools(self, server_name: str, session: ClientSession) -> None:
        """
        Discover available tools from an MCP server

        Args:
            server_name: Name of the server
            session: Active client session
        """
        try:
            # List available tools
            tools_response = await session.list_tools()
            tools = tools_response.tools if hasattr(tools_response, "tools") else []

            # Store tools for this server
            self.tools[server_name] = []

            for tool in tools:
                tool_info = {
                    "server": server_name,
                    "name": tool.name,
                    "description": tool.description
                    if hasattr(tool, "description")
                    else "",
                    "inputSchema": tool.inputSchema
                    if hasattr(tool, "inputSchema")
                    else {},
                }
                self.tools[server_name].append(tool_info)
                self.all_tools.append(tool_info)

            logger.info(
                f"Discovered {len(self.tools[server_name])} tools from '{server_name}'"
            )

        except Exception as e:
            logger.error(f"Failed to discover tools from '{server_name}': {e}")

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """
        Get all discovered tools from all connected servers

        Returns:
            List of tool dictionaries
        """
        return self.all_tools

    def get_tools_for_server(self, server_name: str) -> List[Dict[str, Any]]:
        """
        Get tools for a specific server

        Args:
            server_name: Name of the server

        Returns:
            List of tool dictionaries for the specified server
        """
        return self.tools.get(server_name, [])

    async def call_tool(
        self, server_name: str, tool_name: str, arguments: Dict[str, Any]
    ) -> Any:
        """
        Execute a tool on a specific MCP server

        Args:
            server_name: Name of the server hosting the tool
            tool_name: Name of the tool to execute
            arguments: Tool arguments

        Returns:
            Tool execution result
        """
        if server_name not in self.clients:
            raise ValueError(f"Not connected to MCP server: {server_name}")

        session = self.clients[server_name]

        try:
            logger.info(
                f"Calling tool '{tool_name}' on server '{server_name}' with args: {arguments}"
            )
            result = await session.call_tool(tool_name, arguments)
            logger.info(f"Tool '{tool_name}' executed successfully")
            return result
        except Exception as e:
            logger.error(f"Failed to execute tool '{tool_name}': {e}")
            raise

    async def disconnect_all(self) -> None:
        """Disconnect from all MCP servers"""
        if hasattr(self, "exit_stack"):
            await self.exit_stack.aclose()

        self.clients.clear()
        self.tools.clear()
        self.all_tools.clear()
        logger.info("Disconnected from all MCP servers")

    def format_tools_for_gemini(self) -> List[Dict[str, Any]]:
        """
        Format MCP tools for Google Gemini function calling

        Returns:
            List of tools in Gemini-compatible format
        """
        gemini_tools = []

        for tool in self.all_tools:
            gemini_tool = {
                "name": f"{tool['server']}_{tool['name']}",  # Prefix with server name
                "description": tool["description"],
                "parameters": tool.get("inputSchema", {}),
            }
            gemini_tools.append(gemini_tool)

        return gemini_tools

    def parse_tool_call(self, tool_name: str) -> tuple[str, str]:
        """
        Parse a prefixed tool name to extract server and tool name

        Args:
            tool_name: Tool name in format "server_toolname"

        Returns:
            Tuple of (server_name, actual_tool_name)
        """
        if "_" in tool_name:
            parts = tool_name.split("_", 1)
            return parts[0], parts[1]
        return "", tool_name

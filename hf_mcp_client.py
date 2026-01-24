"""Hugging Face MCP Client - Handles JSON-RPC 2.0 over HTTP"""

import os
import httpx
import logging
import uuid
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class HuggingFaceMCPClient:
    """Client for Hugging Face MCP server via HTTP JSON-RPC 2.0"""

    def __init__(self):
        self.url = os.getenv("HF_MCP_URL", "https://huggingface.co/mcp")
        self.token = os.getenv("HF_TOKEN")
        self.client: Optional[httpx.AsyncClient] = None
        self.session_id: str = str(uuid.uuid4())

    async def start(self):
        """Initialize the httpx client and handshaking with the server"""
        if not self.token:
            logger.warning("HF_TOKEN not found in environment variables.")

        # Initial headers for handshake - MUST include correct Accept
        headers = {
            "Authorization": f"Bearer {self.token}" if self.token else "",
            "Content-Type": "application/json",
            "Accept": "text/event-stream, application/json",
        }
        self.client = httpx.AsyncClient(headers=headers, timeout=30.0)

        # Perform MCP initialize with empty ID first (or let server assign)
        logger.info("Establishing MCP session...")
        init_payload = {
            "jsonrpc": "2.0",
            "id": "init-1",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "hf-mcp-client", "version": "1.0.0"},
            },
        }

        try:
            # We post to the base URL first
            resp = await self.client.post(self.url, json=init_payload)

            if resp.status_code == 200:
                # CAPTURE SERVER SESSION ID
                # The server returns mcp-session-id in lowercase usually
                server_session_id = resp.headers.get(
                    "mcp-session-id"
                ) or resp.headers.get("Mcp-Session-Id")

                if server_session_id:
                    self.session_id = server_session_id
                    logger.info(
                        f"Captured Server-Assigned Session ID: {self.session_id}"
                    )

                    # Update client headers to include this session ID for future requests
                    self.client.headers.update(
                        {
                            "Mcp-Session-Id": self.session_id,
                            # "X-Session-Id": self.session_id # Try without this first if standard is Mcp-Session-Id
                        }
                    )
                else:
                    logger.warning(
                        "Server did not return mcp-session-id header! Using generated one."
                    )

                # Send initialized notification
                notif = {"jsonrpc": "2.0", "method": "notifications/initialized"}

                # IMPORTANT: Some servers need the ID in query param too?
                # Our research showed the header was returned. Let's rely on header first.
                await self.client.post(self.url, json=notif)
                logger.info(
                    f"HuggingFaceMCPClient session established: {self.session_id}"
                )
            else:
                logger.error(
                    f"Failed to initialize HF MCP session: {resp.status_code} - {resp.text}"
                )
        except Exception as e:
            logger.error(f"Exception during HF MCP initialization: {str(e)}")

    async def stop(self):
        """Close the httpx client"""
        if self.client:
            await self.client.aclose()
            self.client = None
            logger.info("HuggingFaceMCPClient closed")

    async def _request(
        self, method: str, params: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Send a JSON-RPC 2.0 request"""
        if not self.client:
            await self.start()

        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": method,
            "params": params or {},
        }

        # Include sessionId in query params for proxies that require it
        request_url = f"{self.url}?sessionId={self.session_id}"

        try:
            response = await self.client.post(request_url, json=payload)

            if response.status_code != 200:
                error_msg = f"HF MCP error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {"error": {"code": response.status_code, "message": error_msg}}

            data = response.json()

            if "error" in data:
                logger.error(f"MCP RPC error: {data['error']}")
                return data

            return data.get("result")

        except Exception as e:
            error_msg = f"Exception during HF MCP request: {str(e)}"
            logger.error(error_msg)
            return {"error": {"code": -32000, "message": error_msg}}

    async def list_tools(self) -> Dict[str, Any]:
        """Calls method 'tools/list'"""
        result = await self._request("tools/list")
        if isinstance(result, dict) and "error" in result:
            return {"count": 0, "tools": []}

        # Adjusting to potential differences in response format
        tools = result.get("tools", []) if isinstance(result, dict) else []
        return {"count": len(tools), "tools": tools}

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Calls method 'tools/call'"""
        params = {"name": name, "arguments": arguments}
        return await self._request("tools/call", params)

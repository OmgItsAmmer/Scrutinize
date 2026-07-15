import asyncio
import sys
import os
import logging
from typing import Any
from app.core.config import Settings

logger = logging.getLogger(__name__)

PDF_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "generate_pdf",
        "description": "Generate a formatted PDF document with a title and content.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["title", "content"],
        },
    },
}

FLOWCHART_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "generate_flowchart",
        "description": "Generate a Mermaid diagram flowchart from a title and description.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["title", "content"],
        },
    },
}

WEB_SEARCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web for real-time technology/AI news, startup funding, or tech events.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "default": 3},
            },
            "required": ["query"],
        },
    },
}

FALLBACK_SCHEMAS = [PDF_TOOL_SCHEMA, FLOWCHART_TOOL_SCHEMA, WEB_SEARCH_SCHEMA]


class McpClientManager:
    """Synchronous manager client for the unified Scrutinize MCP Server."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._enabled = settings.mcp_pdf_server_enabled
        self._python_exe = sys.executable
        self._pdf_server_args = ["-m", "app.services.v2.mcp_servers.unified_server"]

    def is_enabled(self) -> bool:
        return self._enabled

    def _call_local_tool_fallback(self, tool_name: str, arguments: dict) -> Any:
        if tool_name == "generate_pdf":
            from app.services.v2.mcp_servers.pdf_generator import generate_pdf
            return generate_pdf(
                title=str(arguments.get("title") or "generated-document"),
                content=str(arguments.get("content") or ""),
            )
        elif tool_name == "generate_flowchart":
            from app.services.v2.mcp_servers.unified_server import generate_flowchart
            return generate_flowchart(
                title=str(arguments.get("title") or "flowchart"),
                content=str(arguments.get("content") or ""),
            )
        elif tool_name == "web_search":
            from app.services.v2.mcp_servers.unified_server import web_search
            return asyncio.run(web_search(
                query=str(arguments.get("query") or ""),
                limit=int(arguments.get("limit") or 3)
            ))
        else:
            raise RuntimeError(f"Unknown local MCP fallback tool: {tool_name}")

    async def _list_tools_async(self) -> list[dict]:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        server_params = StdioServerParameters(
            command=self._python_exe,
            args=self._pdf_server_args,
            env=os.environ.copy()
        )
        
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    
                    openai_tools = []
                    for tool in result.tools:
                        openai_tools.append({
                            "type": "function",
                            "function": {
                                "name": tool.name,
                                "description": tool.description,
                                "parameters": tool.inputSchema
                            }
                        })
                    return openai_tools
        except Exception as e:
            logger.error(f"Error listing MCP tools: {e}")
            return []

    async def _call_tool_async(self, tool_name: str, arguments: dict) -> Any:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        server_params = StdioServerParameters(
            command=self._python_exe,
            args=self._pdf_server_args,
            env=os.environ.copy()
        )
        
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    # Result content is usually a list of content blocks
                    # We will return the text content from the blocks
                    outputs = []
                    for block in result.content:
                        if hasattr(block, "text"):
                            outputs.append(block.text)
                        elif isinstance(block, dict) and "text" in block:
                            outputs.append(block["text"])
                        else:
                            outputs.append(str(block))
                    return "\n".join(outputs)
        except Exception as e:
            logger.error(f"Error calling MCP tool {tool_name}: {e}")
            raise RuntimeError(f"MCP tool execution failed: {e}") from e

    def _run_sync(self, coro):
        import asyncio
        import threading
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            result = None
            exception = None

            def target():
                nonlocal result, exception
                try:
                    result = asyncio.run(coro)
                except Exception as e:
                    exception = e

            t = threading.Thread(target=target)
            t.start()
            t.join()
            if exception:
                raise exception
            return result
        else:
            return asyncio.run(coro)

    def list_tools(self) -> list[dict]:
        if not self._enabled:
            return []
        try:
            tools = self._run_sync(self._list_tools_async())
            return tools or FALLBACK_SCHEMAS
        except Exception as e:
            logger.warning("MCP list_tools failed; using local PDF fallback schema: %s", e)
            return FALLBACK_SCHEMAS

    def call_tool(self, tool_name: str, arguments: dict) -> Any:
        if not self._enabled:
            raise RuntimeError("MCP Server is disabled in config.")
        try:
            return self._run_sync(self._call_tool_async(tool_name, arguments))
        except ModuleNotFoundError as e:
            if e.name != "mcp":
                raise
            logger.info("The 'mcp' package is not installed; attempting local Python fallback for tool: %s", tool_name)
            return self._call_local_tool_fallback(tool_name, arguments)
        except Exception as e:
            logger.warning("MCP tool execution failed; attempting local Python fallback: %s", e)
            return self._call_local_tool_fallback(tool_name, arguments)

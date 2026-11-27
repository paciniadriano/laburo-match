"""MCP tool definitions in the shape a chat model's `bind_tools` takes."""

from typing import Any

from mcp.types import Tool


def to_model_tools(tools: list[Tool]) -> list[dict[str, Any]]:
    """The server already describes each tool with a JSON Schema: pass it through unchanged."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": tool.inputSchema,
            },
        }
        for tool in tools
    ]

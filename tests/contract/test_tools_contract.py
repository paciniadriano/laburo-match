"""What a host sees of the server: tool names, hints and input schemas. No database needed."""

import json
from typing import Any

import pytest
from fastmcp import Client
from mcp.types import Tool

from src.config.settings import Settings
from src.server import create_mcp_server

EXPECTED_TOOLS = {"search_jobs", "screen_batch", "list_jobs"}


@pytest.fixture
async def tools() -> dict[str, Tool]:
    server = create_mcp_server(Settings.from_env_file(None), sources=[])
    async with Client(server) as client:
        return {tool.name: tool for tool in await client.list_tools()}


async def test_the_server_offers_exactly_the_tools_of_this_phase(tools: dict[str, Tool]):
    assert set(tools) == EXPECTED_TOOLS


async def test_every_tool_says_all_four_hints_explicitly(tools: dict[str, Tool]):
    for tool in tools.values():
        assert tool.annotations is not None, tool.name
        hints = tool.annotations
        for hint in ("readOnlyHint", "destructiveHint", "idempotentHint", "openWorldHint"):
            assert getattr(hints, hint) is not None, f"{tool.name} does not set {hint}"


async def test_hints_describe_what_each_tool_really_does(tools: dict[str, Tool]):
    search, screen = tools["search_jobs"].annotations, tools["screen_batch"].annotations
    assert search is not None and screen is not None
    assert search.openWorldHint is True  # it asks external sources
    assert screen.idempotentHint is True  # repeating a call never redoes finished work
    assert not (search.destructiveHint or screen.destructiveHint)
    listing = tools["list_jobs"].annotations
    assert listing is not None and listing.readOnlyHint is True  # it never changes a verdict


async def test_every_tool_has_a_description_for_the_model(tools: dict[str, Tool]):
    for tool in tools.values():
        assert tool.description and len(tool.description) > 40, tool.name


def _complex_keywords(schema: Any) -> list[str]:
    """Union keywords anywhere in a schema: they are what `Optional` and `|` produce."""
    found: list[str] = []
    if isinstance(schema, dict):
        found += [key for key in ("anyOf", "oneOf", "allOf") if key in schema]
        for value in schema.values():
            found += _complex_keywords(value)
    elif isinstance(schema, list):
        for item in schema:
            found += _complex_keywords(item)
    return found


async def test_input_schemas_use_simple_types_only(tools: dict[str, Tool]):
    """Hosts handle `anyOf` badly, so inputs are plain `str`, `int`, `bool`, lists, literals."""
    for tool in tools.values():
        assert _complex_keywords(tool.inputSchema) == [], tool.name
        for name, prop in tool.inputSchema["properties"].items():
            assert prop.get("type") in {"string", "integer", "boolean", "array"}, (tool.name, name)


async def test_the_caller_cannot_choose_the_user(tools: dict[str, Tool]):
    for tool in tools.values():
        assert "user_id" not in tool.inputSchema["properties"], tool.name


async def test_tools_do_not_expose_context_or_internal_parameters(tools: dict[str, Tool]):
    assert set(tools["search_jobs"].inputSchema["properties"]) == {"max_new"}
    assert set(tools["screen_batch"].inputSchema["properties"]) == {"run_id"}
    assert tools["screen_batch"].inputSchema["required"] == ["run_id"]
    assert set(tools["list_jobs"].inputSchema["properties"]) == {"status", "limit", "offset"}


async def test_list_jobs_offers_only_the_statuses_that_exist_in_this_phase(tools: dict[str, Tool]):
    assert tools["list_jobs"].inputSchema["properties"]["status"]["enum"] == ["all", "filtered"]


async def test_tools_declare_a_typed_output(tools: dict[str, Tool]):
    for tool in tools.values():
        assert tool.outputSchema is not None, tool.name
        json.dumps(tool.outputSchema)  # serializable: what the host receives

import pytest
from unittest.mock import AsyncMock, MagicMock
from mcp.server.fastmcp import FastMCP
from src.clients.confluence_client import ConfluenceClient
from src.tools.confluence_tools import register_confluence_tools


@pytest.fixture
def mcp_instance():
    return FastMCP(name="test-mcp", stateless_http=True)


@pytest.fixture
def confluence_client():
    client = MagicMock(spec=ConfluenceClient)
    client._base = "https://confluence.bank.com.pl"
    return client


@pytest.mark.asyncio
async def test_confluence_search_returns_results(mcp_instance, confluence_client):
    confluence_client.search = AsyncMock(return_value={
        "totalSize": 1,
        "results": [
            {
                "id": "123",
                "title": "Architektura AI",
                "space": {"key": "AI", "name": "Zespół AI"},
                "excerpt": "Opis architektury...",
            }
        ],
    })
    register_confluence_tools(mcp_instance, confluence_client)

    tools = {t.name: t for t in mcp_instance._tool_manager._tools.values()}
    result = await tools["confluence_search"].fn(cql='space.key = "AI"')

    assert result["total"] == 1
    assert result["results"][0]["title"] == "Architektura AI"
    assert result["results"][0]["space_key"] == "AI"


@pytest.mark.asyncio
async def test_confluence_get_page(mcp_instance, confluence_client):
    confluence_client.get_page = AsyncMock(return_value={
        "id": "456",
        "title": "Instrukcja",
        "space": {"key": "DEV", "name": "Development"},
        "version": {"number": 3},
        "ancestors": [{"title": "Strona nadrzędna"}],
        "body": {"storage": {"value": "<p>Treść strony</p>"}},
    })
    register_confluence_tools(mcp_instance, confluence_client)

    tools = {t.name: t for t in mcp_instance._tool_manager._tools.values()}
    result = await tools["confluence_get_page"].fn(page_id="456")

    assert result["title"] == "Instrukcja"
    assert result["version"] == 3
    assert result["parent_title"] == "Strona nadrzędna"
    assert "<p>Treść strony</p>" in result["body_html"]

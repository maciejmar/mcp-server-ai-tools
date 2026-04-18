import pytest
from unittest.mock import AsyncMock, MagicMock
from mcp.server.fastmcp import FastMCP
from src.clients.jira_client import JiraClient
from src.tools.jira_tools import register_jira_tools


@pytest.fixture
def mcp_instance():
    return FastMCP(name="test-mcp", stateless_http=True)


@pytest.fixture
def jira_client():
    client = MagicMock(spec=JiraClient)
    client._base = "https://jira.bank.com.pl"
    return client


@pytest.mark.asyncio
async def test_jira_search_returns_issues(mcp_instance, jira_client):
    jira_client.search = AsyncMock(return_value={
        "total": 1,
        "issues": [
            {
                "key": "ZZ-1",
                "fields": {
                    "summary": "Test issue",
                    "status": {"name": "In Progress"},
                    "assignee": {"displayName": "Jan Kowalski"},
                    "priority": {"name": "High"},
                },
            }
        ],
    })
    register_jira_tools(mcp_instance, jira_client)

    tools = {t.name: t for t in mcp_instance._tool_manager._tools.values()}
    result = await tools["jira_search"].fn(jql="project = ZZ", max_results=10)

    assert result["total"] == 1
    assert result["issues"][0]["key"] == "ZZ-1"
    assert result["issues"][0]["status"] == "In Progress"


@pytest.mark.asyncio
async def test_jira_search_handles_http_error(mcp_instance, jira_client):
    import httpx
    jira_client.search = AsyncMock(
        side_effect=httpx.HTTPStatusError("error", request=MagicMock(), response=MagicMock(status_code=401))
    )
    register_jira_tools(mcp_instance, jira_client)

    tools = {t.name: t for t in mcp_instance._tool_manager._tools.values()}
    result = await tools["jira_search"].fn(jql="project = ZZ")

    assert "error" in result
    assert "401" in result["error"]


@pytest.mark.asyncio
async def test_jira_transition_not_found(mcp_instance, jira_client):
    jira_client.get_transitions = AsyncMock(return_value={
        "transitions": [{"id": "1", "name": "In Progress"}, {"id": "2", "name": "Done"}]
    })
    register_jira_tools(mcp_instance, jira_client)

    tools = {t.name: t for t in mcp_instance._tool_manager._tools.values()}
    result = await tools["jira_transition"].fn(issue_key="ZZ-1", transition_name="Nonexistent")

    assert "error" in result
    assert "available_transitions" in result


@pytest.mark.asyncio
async def test_jira_transition_success(mcp_instance, jira_client):
    jira_client.get_transitions = AsyncMock(return_value={
        "transitions": [{"id": "31", "name": "Done"}]
    })
    jira_client.transition = AsyncMock(return_value=None)
    register_jira_tools(mcp_instance, jira_client)

    tools = {t.name: t for t in mcp_instance._tool_manager._tools.values()}
    result = await tools["jira_transition"].fn(issue_key="ZZ-1", transition_name="Done")

    assert result["success"] is True
    assert result["new_status"] == "Done"

import pytest
from mcp.server.fastmcp import FastMCP

from src.config import settings
from src.tools.log_tools import register_log_tools


@pytest.fixture
def mcp_instance():
    return FastMCP(name="test-mcp", stateless_http=True)


@pytest.mark.asyncio
async def test_log_read_filtered_redacts_and_filters(mcp_instance, tmp_path, monkeypatch):
    log_file = tmp_path / "app.log"
    log_file.write_text(
        "\n".join(
            [
                "INFO healthcheck ok",
                "DEBUG token=secret-value",
                "ERROR Missing required environment variable DATABASE_URL",
                "WARN connection refused password=hidden",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "MCP_ALLOWED_LOG_PATHS", str(log_file))

    register_log_tools(mcp_instance)
    tools = {t.name: t for t in mcp_instance._tool_manager._tools.values()}
    result = await tools["log_read_filtered"].fn(path=str(log_file), max_lines=50)

    assert result["filtered_line_count"] == 2
    assert "healthcheck" not in "\n".join(result["lines"])
    assert "secret-value" not in "\n".join(result["lines"])
    assert "password=[REDACTED]" in "\n".join(result["lines"])


@pytest.mark.asyncio
async def test_log_read_filtered_rejects_path_outside_allowlist(mcp_instance, tmp_path, monkeypatch):
    allowed = tmp_path / "allowed.log"
    forbidden = tmp_path / "forbidden.log"
    allowed.write_text("ERROR allowed", encoding="utf-8")
    forbidden.write_text("ERROR forbidden", encoding="utf-8")
    monkeypatch.setattr(settings, "MCP_ALLOWED_LOG_PATHS", str(allowed))

    register_log_tools(mcp_instance)
    tools = {t.name: t for t in mcp_instance._tool_manager._tools.values()}
    result = await tools["log_read_filtered"].fn(path=str(forbidden), max_lines=50)

    assert "error" in result
    assert result["lines"] == []

import os
import sys
import logging

# Ładuj .env przed importem settings
from dotenv import load_dotenv
load_dotenv()

from src.middleware.logging import configure_json_logging
from src.config import settings

configure_json_logging(settings.MCP_LOG_LEVEL)
logger = logging.getLogger(__name__)

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse

from src.clients.jira_client import JiraClient
from src.clients.confluence_client import ConfluenceClient
from src.clients.grafana_client import GrafanaClient
from src.clients.bitbucket_client import BitbucketClient
from src.clients.ollama_client import OllamaClient

from src.tools.jira_tools import register_jira_tools
from src.tools.confluence_tools import register_confluence_tools
from src.tools.grafana_tools import register_grafana_tools
from src.tools.bitbucket_tools import register_bitbucket_tools
from src.tools.infra_tools import register_infra_tools

from src.middleware.auth import APIKeyMiddleware
from src.middleware.logging import AuditLoggingMiddleware

# Wykryj ścieżkę do CA bundle — użyj tylko jeśli plik istnieje
_ca_bundle: str | None = settings.TLS_CA_BUNDLE if os.path.isfile(settings.TLS_CA_BUNDLE) else None

# Inicjalizacja klientów HTTP
jira_client = JiraClient(
    base_url=settings.JIRA_URL,
    token=settings.JIRA_PAT,
    timeout=settings.JIRA_TIMEOUT,
    ca_bundle=_ca_bundle,
)
confluence_client = ConfluenceClient(
    base_url=settings.CONFLUENCE_URL,
    token=settings.CONFLUENCE_PAT,
    timeout=settings.CONFLUENCE_TIMEOUT,
    ca_bundle=_ca_bundle,
)
grafana_client = GrafanaClient(
    base_url=settings.GRAFANA_URL,
    token=settings.GRAFANA_TOKEN,
    timeout=settings.GRAFANA_TIMEOUT,
    ca_bundle=_ca_bundle,
)
bitbucket_client = BitbucketClient(
    base_url=settings.BITBUCKET_URL,
    token=settings.BITBUCKET_PAT,
    timeout=settings.BITBUCKET_TIMEOUT,
    ca_bundle=_ca_bundle,
)
ollama_client = OllamaClient(
    base_url=settings.OLLAMA_URL,
    timeout=settings.OLLAMA_TIMEOUT,
)

# Serwer MCP
mcp = FastMCP(
    name="bgk-ai-mcp",
    stateless_http=True,
)

# Rejestracja narzędzi
register_jira_tools(mcp, jira_client)
register_confluence_tools(mcp, confluence_client)
register_grafana_tools(mcp, grafana_client)
register_bitbucket_tools(mcp, bitbucket_client)
register_infra_tools(mcp, ollama_client)

logger.info("MCP tools registered", extra={"tool_count": len(mcp._tool_manager._tools)})


async def health(request):
    return JSONResponse({"status": "ok", "service": "bgk-ai-mcp"})


def build_app():
    """Buduje Starlette ASGI app z MCP serverem i middleware."""
    mcp_app = mcp.streamable_http_app()

    # Dodaj health endpoint do MCP app lub opakuj w Starlette
    from starlette.routing import Mount
    app = Starlette(
        routes=[
            Route("/health", health),
            Mount("/", app=mcp_app),
        ]
    )

    # Middleware (kolejność: najpierw logging, potem auth)
    app.add_middleware(APIKeyMiddleware, api_key=settings.MCP_API_KEY)
    app.add_middleware(AuditLoggingMiddleware)

    return app


app = build_app()

if __name__ == "__main__":
    import uvicorn

    logger.info(
        "Starting BGK AI MCP Server",
        extra={"host": "0.0.0.0", "port": settings.MCP_SERVER_PORT},
    )
    uvicorn.run(
        "src.server:app",
        host="0.0.0.0",
        port=settings.MCP_SERVER_PORT,
        log_config=None,  # używamy własnego loggera
    )

import logging
from mcp.server.fastmcp import FastMCP
from src.clients.grafana_client import GrafanaClient
import httpx

logger = logging.getLogger(__name__)


def register_grafana_tools(mcp: FastMCP, client: GrafanaClient) -> None:
    """Rejestruje wszystkie narzędzia Grafana w instancji MCP servera."""

    @mcp.tool()
    async def grafana_search_dashboards(query: str) -> dict:
        """Wyszukuje dashboardy w Grafanie po nazwie lub tagu.

        Użyj gdy chcesz znaleźć dashboard monitoringu dla konkretnej aplikacji lub metryki.

        Args:
            query: Fraza wyszukiwania, np. 'mcp-server', 'gpu', 'api-latency'.

        Returns:
            Słownik z listą 'dashboards' zawierającą: uid, title, url, folder_title.
        """
        logger.info("grafana_search_dashboards called", extra={"tool": "grafana_search_dashboards", "query": query})
        try:
            results = await client.search_dashboards(query)
            return {
                "dashboards": [
                    {
                        "uid": d.get("uid"),
                        "title": d.get("title"),
                        "url": f"{client._base}{d.get('url', '')}",
                        "folder_title": d.get("folderTitle", "General"),
                        "tags": d.get("tags", []),
                    }
                    for d in results
                ]
            }
        except httpx.HTTPStatusError as e:
            return {"error": f"Grafana zwróciła błąd {e.response.status_code}", "detail": str(e)}
        except httpx.RequestError as e:
            return {"error": "Błąd połączenia z Grafaną", "detail": str(e)}

    @mcp.tool()
    async def grafana_query_datasource(
        datasource_uid: str,
        query: str,
        from_time: str = "now-1h",
        to_time: str = "now",
    ) -> dict:
        """Wykonuje zapytanie do datasource Grafany (np. Prometheus, Loki).

        Użyj gdy chcesz pobrać dane metryk lub logów z określonego zakresu czasu.
        Dla Prometheusa użyj składni PromQL, np. 'rate(http_requests_total[5m])'.

        Args:
            datasource_uid: UID datasource z Grafany (znajdź w konfiguracji datasource).
            query: Zapytanie w języku właściwym dla datasource (PromQL, LogQL, SQL).
            from_time: Początek przedziału czasowego. Format: 'now-1h', 'now-24h',
                       'now-7d' lub Unix timestamp w ms (domyślnie 'now-1h').
            to_time: Koniec przedziału czasowego (domyślnie 'now').

        Returns:
            Słownik z danymi metryk: lista serii z timestamps i values.
        """
        logger.info("grafana_query_datasource called", extra={
            "tool": "grafana_query_datasource", "datasource_uid": datasource_uid,
            "from_time": from_time, "to_time": to_time
        })
        try:
            result = await client.query_datasource(datasource_uid, query, from_time, to_time)
            return result
        except httpx.HTTPStatusError as e:
            return {"error": f"Grafana zwróciła błąd {e.response.status_code}", "detail": str(e)}
        except httpx.RequestError as e:
            return {"error": "Błąd połączenia z Grafaną", "detail": str(e)}

    @mcp.tool()
    async def grafana_get_alerts(state: str = "firing") -> dict:
        """Pobiera aktywne alerty z Grafana Alertmanager.

        Użyj gdy chcesz sprawdzić czy są aktywne incydenty lub alarmy w systemach.

        Args:
            state: Stan alertów do pobrania: 'firing' (aktywne, domyślnie),
                   'pending' (oczekujące), 'inactive' (nieaktywne).

        Returns:
            Słownik z listą 'alerts' zawierającą: name, state, severity,
            labels, annotations (summary, description), starts_at.
        """
        logger.info("grafana_get_alerts called", extra={"tool": "grafana_get_alerts", "state": state})
        try:
            alerts = await client.get_alerts(state)
            return {
                "count": len(alerts),
                "alerts": [
                    {
                        "name": a.get("labels", {}).get("alertname", "Unknown"),
                        "state": a.get("status", {}).get("state", state),
                        "severity": a.get("labels", {}).get("severity", "unknown"),
                        "labels": a.get("labels", {}),
                        "summary": a.get("annotations", {}).get("summary", ""),
                        "description": a.get("annotations", {}).get("description", ""),
                        "starts_at": a.get("startsAt", ""),
                    }
                    for a in alerts
                ],
            }
        except httpx.HTTPStatusError as e:
            return {"error": f"Grafana zwróciła błąd {e.response.status_code}", "detail": str(e)}
        except httpx.RequestError as e:
            return {"error": "Błąd połączenia z Grafaną", "detail": str(e)}

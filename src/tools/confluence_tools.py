import logging
from mcp.server.fastmcp import FastMCP
from src.clients.confluence_client import ConfluenceClient
import httpx

logger = logging.getLogger(__name__)


def register_confluence_tools(mcp: FastMCP, client: ConfluenceClient) -> None:
    """Rejestruje wszystkie narzędzia Confluence w instancji MCP servera."""

    @mcp.tool()
    async def confluence_search(cql: str, max_results: int = 10) -> dict:
        """Wyszukuje strony i treści w Confluence za pomocą zapytania CQL.

        Użyj gdy chcesz znaleźć dokumentację, wiki lub inne treści w Confluence.
        Przykładowe zapytania CQL:
        - 'text ~ "architektura" AND space.key = "AI"'
        - 'title = "Instrukcja wdrożenia" AND type = page'
        - 'space.key = "DEV" AND lastModified >= "2024-01-01"'

        Args:
            cql: Zapytanie CQL (Confluence Query Language).
            max_results: Maksymalna liczba wyników (1-50, domyślnie 10).

        Returns:
            Słownik z 'total' i listą 'results' zawierającą: id, title, space_key,
            space_name, url, excerpt (fragment dopasowanego tekstu).
        """
        logger.info("confluence_search called", extra={"tool": "confluence_search", "cql": cql})
        try:
            data = await client.search(cql, max_results=min(max_results, 50))
            return {
                "total": data.get("totalSize", 0),
                "results": [
                    {
                        "id": item.get("id"),
                        "title": item.get("title"),
                        "space_key": item.get("space", {}).get("key"),
                        "space_name": item.get("space", {}).get("name"),
                        "url": f"{client._base}/pages/viewpage.action?pageId={item.get('id')}",
                        "excerpt": item.get("excerpt", ""),
                    }
                    for item in data.get("results", [])
                ],
            }
        except httpx.HTTPStatusError as e:
            return {"error": f"Confluence zwrócił błąd {e.response.status_code}", "detail": str(e)}
        except httpx.RequestError as e:
            return {"error": "Błąd połączenia z Confluence", "detail": str(e)}

    @mcp.tool()
    async def confluence_get_page(page_id: str) -> dict:
        """Pobiera pełną treść strony Confluence.

        Użyj gdy znasz ID strony (z wyników wyszukiwania) i chcesz przeczytać jej zawartość.

        Args:
            page_id: Numeryczny identyfikator strony Confluence, np. '123456'.

        Returns:
            Słownik z: title, space_key, body_html (treść w formacie HTML storage),
            body_text (uproszczona wersja tekstowa), version, url, parent_title.
        """
        logger.info("confluence_get_page called", extra={"tool": "confluence_get_page", "page_id": page_id})
        try:
            page = await client.get_page(page_id)
            body_html = page.get("body", {}).get("storage", {}).get("value", "")
            ancestors = page.get("ancestors", [])
            return {
                "id": page.get("id"),
                "title": page.get("title"),
                "space_key": page.get("space", {}).get("key"),
                "space_name": page.get("space", {}).get("name"),
                "version": page.get("version", {}).get("number"),
                "url": f"{client._base}/pages/viewpage.action?pageId={page.get('id')}",
                "parent_title": ancestors[-1].get("title") if ancestors else None,
                "body_html": body_html,
            }
        except httpx.HTTPStatusError as e:
            return {"error": f"Confluence zwrócił błąd {e.response.status_code}", "detail": str(e)}
        except httpx.RequestError as e:
            return {"error": "Błąd połączenia z Confluence", "detail": str(e)}

    @mcp.tool()
    async def confluence_create_page(
        space_key: str,
        title: str,
        body: str,
        parent_id: str | None = None,
    ) -> dict:
        """Tworzy nową stronę w Confluence.

        Użyj gdy chcesz opublikować dokumentację, raport lub notatkę.
        Treść (body) powinna być w formacie Confluence Storage Format (XHTML-based).

        Args:
            space_key: Klucz przestrzeni (space) Confluence, np. 'AI', 'DEV', 'OPS'.
            title: Tytuł nowej strony.
            body: Treść strony w formacie Confluence Storage Format (HTML/XHTML).
                  Przykład: '<p>Treść strony</p><h2>Sekcja</h2><p>...</p>'
            parent_id: (opcjonalnie) ID strony nadrzędnej — jeśli podane, nowa strona
                       będzie podstroną wskazanej strony.

        Returns:
            Słownik z 'id', 'title' i 'url' nowo utworzonej strony.
        """
        logger.info("confluence_create_page called", extra={
            "tool": "confluence_create_page", "space_key": space_key, "title": title
        })
        try:
            page = await client.create_page(space_key, title, body, parent_id)
            return {
                "id": page.get("id"),
                "title": page.get("title"),
                "url": f"{client._base}/pages/viewpage.action?pageId={page.get('id')}",
            }
        except httpx.HTTPStatusError as e:
            return {"error": f"Confluence zwrócił błąd {e.response.status_code}", "detail": str(e)}
        except httpx.RequestError as e:
            return {"error": "Błąd połączenia z Confluence", "detail": str(e)}

    @mcp.tool()
    async def confluence_update_page(page_id: str, title: str, body: str) -> dict:
        """Aktualizuje istniejącą stronę Confluence.

        Wersja strony jest automatycznie pobierana i inkrementowana.
        UWAGA: Całkowicie zastępuje dotychczasową treść podanym body.

        Args:
            page_id: Numeryczny identyfikator strony do zaktualizowania.
            title: Nowy tytuł strony (może być taki sam jak poprzedni).
            body: Nowa treść w formacie Confluence Storage Format (HTML/XHTML).
                  Całkowicie zastępuje poprzednią treść.

        Returns:
            Potwierdzenie z 'id', 'title', 'version' (nowy numer wersji) i 'url'.
        """
        logger.info("confluence_update_page called", extra={
            "tool": "confluence_update_page", "page_id": page_id, "title": title
        })
        try:
            page = await client.update_page(page_id, title, body)
            return {
                "success": True,
                "id": page.get("id"),
                "title": page.get("title"),
                "version": page.get("version", {}).get("number"),
                "url": f"{client._base}/pages/viewpage.action?pageId={page.get('id')}",
            }
        except httpx.HTTPStatusError as e:
            return {"error": f"Confluence zwrócił błąd {e.response.status_code}", "detail": str(e)}
        except httpx.RequestError as e:
            return {"error": "Błąd połączenia z Confluence", "detail": str(e)}

import logging
from mcp.server.fastmcp import FastMCP
from src.clients.jira_client import JiraClient
import httpx

logger = logging.getLogger(__name__)


def register_jira_tools(mcp: FastMCP, client: JiraClient) -> None:
    """Rejestruje wszystkie narzędzia Jira w instancji MCP servera."""

    @mcp.tool()
    async def jira_search(jql: str, max_results: int = 20) -> dict:
        """Wyszukuje tickety Jira za pomocą zapytania JQL.

        Użyj tego narzędzia gdy chcesz znaleźć tickety spełniające określone kryteria.
        Przykładowe zapytania JQL:
        - 'project = ZZ AND status = "In Progress"'
        - 'assignee = currentUser() AND priority = High'
        - 'created >= -7d ORDER BY created DESC'

        Args:
            jql: Zapytanie w języku JQL (Jira Query Language).
            max_results: Maksymalna liczba wyników (1-50, domyślnie 20).

        Returns:
            Słownik z kluczami 'total' (łączna liczba wyników) i 'issues' (lista ticketów
            z polami: key, summary, status, assignee, priority).
        """
        logger.info("jira_search called", extra={"tool": "jira_search", "jql": jql, "max_results": max_results})
        try:
            results = await client.search(jql, max_results=min(max_results, 50))
            return {
                "total": results["total"],
                "issues": [
                    {
                        "key": issue["key"],
                        "summary": issue["fields"]["summary"],
                        "status": issue["fields"]["status"]["name"],
                        "assignee": (issue["fields"].get("assignee") or {}).get("displayName", "Unassigned"),
                        "priority": (issue["fields"].get("priority") or {}).get("name", "Unknown"),
                    }
                    for issue in results["issues"]
                ],
            }
        except httpx.HTTPStatusError as e:
            return {"error": f"Jira zwrócił błąd {e.response.status_code}", "detail": str(e)}
        except httpx.RequestError as e:
            return {"error": "Błąd połączenia z Jirą", "detail": str(e)}

    @mcp.tool()
    async def jira_get_issue(issue_key: str) -> dict:
        """Pobiera szczegółowe informacje o konkretnym tickecie Jira.

        Użyj gdy znasz klucz ticketa (np. ZZ-123) i chcesz poznać jego pełne szczegóły
        włącznie z opisem, komentarzami i historią.

        Args:
            issue_key: Klucz ticketa, np. 'ZZ-123' lub 'PROJ-456'.

        Returns:
            Słownik z pełnymi danymi ticketa: key, summary, status, assignee, priority,
            description, labels, comments (lista ostatnich komentarzy), reporter,
            created, updated.
        """
        logger.info("jira_get_issue called", extra={"tool": "jira_get_issue", "issue_key": issue_key})
        try:
            issue = await client.get_issue(issue_key)
            fields = issue["fields"]
            comments = fields.get("comment", {}).get("comments", [])
            return {
                "key": issue["key"],
                "summary": fields["summary"],
                "status": fields["status"]["name"],
                "assignee": (fields.get("assignee") or {}).get("displayName", "Unassigned"),
                "reporter": (fields.get("reporter") or {}).get("displayName", "Unknown"),
                "priority": (fields.get("priority") or {}).get("name", "Unknown"),
                "issue_type": fields.get("issuetype", {}).get("name", "Unknown"),
                "description": fields.get("description", ""),
                "labels": fields.get("labels", []),
                "created": fields.get("created", ""),
                "updated": fields.get("updated", ""),
                "comments": [
                    {
                        "author": (c.get("author") or {}).get("displayName", "Unknown"),
                        "body": c.get("body", ""),
                        "created": c.get("created", ""),
                    }
                    for c in comments[-10:]  # ostatnie 10 komentarzy
                ],
            }
        except httpx.HTTPStatusError as e:
            return {"error": f"Jira zwrócił błąd {e.response.status_code}", "detail": str(e)}
        except httpx.RequestError as e:
            return {"error": "Błąd połączenia z Jirą", "detail": str(e)}

    @mcp.tool()
    async def jira_create_issue(
        project_key: str,
        summary: str,
        description: str,
        issue_type: str = "Task",
    ) -> dict:
        """Tworzy nowy ticket w Jirze.

        Użyj gdy chcesz zarejestrować nowe zadanie, błąd lub historię użytkownika.

        Args:
            project_key: Klucz projektu Jira, np. 'ZZ' lub 'PORTAL'.
            summary: Tytuł ticketa (krótki, opisowy).
            description: Szczegółowy opis zadania/problemu.
            issue_type: Typ ticketa: 'Task', 'Bug', 'Story', 'Epic' (domyślnie 'Task').

        Returns:
            Słownik z kluczem 'key' (np. 'ZZ-124') i 'url' nowo utworzonego ticketa.
        """
        logger.info("jira_create_issue called", extra={
            "tool": "jira_create_issue", "project_key": project_key, "issue_type": issue_type
        })
        try:
            result = await client.create_issue(project_key, summary, description, issue_type)
            return {
                "key": result["key"],
                "id": result["id"],
                "url": f"{client._base}/browse/{result['key']}",
            }
        except httpx.HTTPStatusError as e:
            return {"error": f"Jira zwrócił błąd {e.response.status_code}", "detail": str(e)}
        except httpx.RequestError as e:
            return {"error": "Błąd połączenia z Jirą", "detail": str(e)}

    @mcp.tool()
    async def jira_add_comment(issue_key: str, comment: str) -> dict:
        """Dodaje komentarz do ticketa Jira.

        Użyj gdy chcesz dołączyć notatkę, aktualizację statusu lub odpowiedź do istniejącego ticketa.

        Args:
            issue_key: Klucz ticketa, np. 'ZZ-123'.
            comment: Treść komentarza (obsługuje Jira markup).

        Returns:
            Potwierdzenie z 'id' dodanego komentarza i timestampem 'created'.
        """
        logger.info("jira_add_comment called", extra={"tool": "jira_add_comment", "issue_key": issue_key})
        try:
            result = await client.add_comment(issue_key, comment)
            return {
                "success": True,
                "comment_id": result.get("id"),
                "created": result.get("created"),
            }
        except httpx.HTTPStatusError as e:
            return {"error": f"Jira zwrócił błąd {e.response.status_code}", "detail": str(e)}
        except httpx.RequestError as e:
            return {"error": "Błąd połączenia z Jirą", "detail": str(e)}

    @mcp.tool()
    async def jira_get_transitions(issue_key: str) -> dict:
        """Pobiera dostępne przejścia statusów dla ticketa Jira.

        Użyj PRZED wywołaniem jira_transition, aby poznać dostępne przejścia i ich ID.

        Args:
            issue_key: Klucz ticketa, np. 'ZZ-123'.

        Returns:
            Lista dostępnych przejść z polami: id, name (np. 'In Progress', 'Done').
        """
        logger.info("jira_get_transitions called", extra={"tool": "jira_get_transitions", "issue_key": issue_key})
        try:
            result = await client.get_transitions(issue_key)
            return {
                "transitions": [
                    {"id": t["id"], "name": t["name"]}
                    for t in result.get("transitions", [])
                ]
            }
        except httpx.HTTPStatusError as e:
            return {"error": f"Jira zwrócił błąd {e.response.status_code}", "detail": str(e)}
        except httpx.RequestError as e:
            return {"error": "Błąd połączenia z Jirą", "detail": str(e)}

    @mcp.tool()
    async def jira_transition(issue_key: str, transition_name: str) -> dict:
        """Zmienia status ticketa Jira (np. z 'To Do' na 'In Progress').

        Użyj gdy chcesz przepchnąć ticket przez workflow. Najpierw sprawdź dostępne
        przejścia narzędziem jira_get_transitions.

        Args:
            issue_key: Klucz ticketa, np. 'ZZ-123'.
            transition_name: Nazwa przejścia, np. 'In Progress', 'Done', 'In Review'.
                             Wielkość liter nie ma znaczenia.

        Returns:
            Potwierdzenie zmiany lub błąd jeśli przejście nie istnieje.
        """
        logger.info("jira_transition called", extra={
            "tool": "jira_transition", "issue_key": issue_key, "transition_name": transition_name
        })
        try:
            transitions_data = await client.get_transitions(issue_key)
            transitions = transitions_data.get("transitions", [])
            match = next(
                (t for t in transitions if t["name"].lower() == transition_name.lower()),
                None,
            )
            if not match:
                available = [t["name"] for t in transitions]
                return {
                    "error": f"Przejście '{transition_name}' nie istnieje.",
                    "available_transitions": available,
                }
            await client.transition(issue_key, match["id"])
            return {"success": True, "issue_key": issue_key, "new_status": match["name"]}
        except httpx.HTTPStatusError as e:
            return {"error": f"Jira zwrócił błąd {e.response.status_code}", "detail": str(e)}
        except httpx.RequestError as e:
            return {"error": "Błąd połączenia z Jirą", "detail": str(e)}

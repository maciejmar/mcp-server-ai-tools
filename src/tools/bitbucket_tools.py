import logging
from mcp.server.fastmcp import FastMCP
from src.clients.bitbucket_client import BitbucketClient
import httpx

logger = logging.getLogger(__name__)


def register_bitbucket_tools(mcp: FastMCP, client: BitbucketClient) -> None:
    """Rejestruje wszystkie narzędzia Bitbucket w instancji MCP servera."""

    @mcp.tool()
    async def bitbucket_list_repos(project_key: str) -> dict:
        """Wyświetla listę repozytoriów w projekcie Bitbucket.

        Użyj gdy chcesz sprawdzić jakie repozytoria istnieją w danym projekcie.

        Args:
            project_key: Klucz projektu Bitbucket, np. 'AI', 'PORTAL', 'INFRA'.

        Returns:
            Słownik z listą 'repos' zawierającą: name, slug, clone_url_ssh,
            clone_url_http, default_branch, description.
        """
        logger.info("bitbucket_list_repos called", extra={"tool": "bitbucket_list_repos", "project_key": project_key})
        try:
            data = await client.list_repos(project_key)
            repos = []
            for repo in data.get("values", []):
                clone_links = {
                    link["name"]: link["href"]
                    for link in repo.get("links", {}).get("clone", [])
                }
                repos.append({
                    "name": repo.get("name"),
                    "slug": repo.get("slug"),
                    "description": repo.get("description", ""),
                    "default_branch": repo.get("defaultBranch", {}).get("displayId", "main"),
                    "clone_url_http": clone_links.get("http", ""),
                    "clone_url_ssh": clone_links.get("ssh", ""),
                    "state": repo.get("state"),
                })
            return {"total": data.get("size", len(repos)), "repos": repos}
        except httpx.HTTPStatusError as e:
            return {"error": f"Bitbucket zwrócił błąd {e.response.status_code}", "detail": str(e)}
        except httpx.RequestError as e:
            return {"error": "Błąd połączenia z Bitbucket", "detail": str(e)}

    @mcp.tool()
    async def bitbucket_get_file(
        project_key: str,
        repo_slug: str,
        file_path: str,
        branch: str = "main",
    ) -> dict:
        """Pobiera zawartość pliku z repozytorium Bitbucket.

        Użyj gdy chcesz przeczytać kod źródłowy, konfigurację lub inny plik z repo.

        Args:
            project_key: Klucz projektu Bitbucket, np. 'AI'.
            repo_slug: Slug repozytorium, np. 'ai-dev-agent', 'bgk-mcp-server'.
            file_path: Ścieżka do pliku w repo, np. 'src/main.py', 'docker-compose.yml'.
            branch: Gałąź lub commit SHA (domyślnie 'main').

        Returns:
            Słownik z: content (zawartość pliku), file_path, branch.
        """
        logger.info("bitbucket_get_file called", extra={
            "tool": "bitbucket_get_file", "project_key": project_key,
            "repo_slug": repo_slug, "file_path": file_path
        })
        try:
            return await client.get_file(project_key, repo_slug, file_path, branch)
        except httpx.HTTPStatusError as e:
            return {"error": f"Bitbucket zwrócił błąd {e.response.status_code}", "detail": str(e)}
        except httpx.RequestError as e:
            return {"error": "Błąd połączenia z Bitbucket", "detail": str(e)}

    @mcp.tool()
    async def bitbucket_list_prs(
        project_key: str,
        repo_slug: str,
        state: str = "OPEN",
    ) -> dict:
        """Wyświetla Pull Requesty w repozytorium Bitbucket.

        Użyj gdy chcesz sprawdzić jakie PR czekają na review lub zostały już zmergowane.

        Args:
            project_key: Klucz projektu Bitbucket, np. 'AI'.
            repo_slug: Slug repozytorium, np. 'bgk-mcp-server'.
            state: Stan PR: 'OPEN' (otwarte, domyślnie), 'MERGED', 'DECLINED'.

        Returns:
            Słownik z listą 'pull_requests' zawierającą: id, title, author,
            source_branch, target_branch, reviewers, created_date, updated_date.
        """
        logger.info("bitbucket_list_prs called", extra={
            "tool": "bitbucket_list_prs", "project_key": project_key,
            "repo_slug": repo_slug, "state": state
        })
        try:
            data = await client.list_prs(project_key, repo_slug, state)
            prs = [
                {
                    "id": pr.get("id"),
                    "title": pr.get("title"),
                    "description": pr.get("description", ""),
                    "state": pr.get("state"),
                    "author": pr.get("author", {}).get("user", {}).get("displayName", "Unknown"),
                    "source_branch": pr.get("fromRef", {}).get("displayId", ""),
                    "target_branch": pr.get("toRef", {}).get("displayId", ""),
                    "reviewers": [
                        {
                            "name": r.get("user", {}).get("displayName", ""),
                            "approved": r.get("approved", False),
                        }
                        for r in pr.get("reviewers", [])
                    ],
                    "created_date": pr.get("createdDate"),
                    "updated_date": pr.get("updatedDate"),
                }
                for pr in data.get("values", [])
            ]
            return {"total": data.get("size", len(prs)), "pull_requests": prs}
        except httpx.HTTPStatusError as e:
            return {"error": f"Bitbucket zwrócił błąd {e.response.status_code}", "detail": str(e)}
        except httpx.RequestError as e:
            return {"error": "Błąd połączenia z Bitbucket", "detail": str(e)}

    @mcp.tool()
    async def bitbucket_get_pr_diff(
        project_key: str,
        repo_slug: str,
        pr_id: int,
    ) -> dict:
        """Pobiera diff (unified format) Pull Requesta z Bitbucket.

        Użyj gdy chcesz przejrzeć zmiany kodu w konkretnym PR przed review lub mergem.

        Args:
            project_key: Klucz projektu Bitbucket, np. 'AI'.
            repo_slug: Slug repozytorium, np. 'bgk-mcp-server'.
            pr_id: Numeryczny ID Pull Requesta.

        Returns:
            Słownik z 'diff' (treść diffa w unified format) i 'pr_id'.
        """
        logger.info("bitbucket_get_pr_diff called", extra={
            "tool": "bitbucket_get_pr_diff", "project_key": project_key,
            "repo_slug": repo_slug, "pr_id": pr_id
        })
        try:
            diff = await client.get_pr_diff(project_key, repo_slug, pr_id)
            return {"pr_id": pr_id, "diff": diff}
        except httpx.HTTPStatusError as e:
            return {"error": f"Bitbucket zwrócił błąd {e.response.status_code}", "detail": str(e)}
        except httpx.RequestError as e:
            return {"error": "Błąd połączenia z Bitbucket", "detail": str(e)}

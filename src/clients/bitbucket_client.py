import httpx
from typing import Any


class BitbucketClient:
    def __init__(self, base_url: str, token: str, timeout: float = 30.0, ca_bundle: str | None = None):
        self._base = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        self._timeout = timeout
        self._verify: str | bool = ca_bundle if ca_bundle else True

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            headers=self._headers,
            timeout=self._timeout,
            verify=self._verify,
        )

    async def list_repos(self, project_key: str) -> dict[str, Any]:
        async with self._client() as c:
            r = await c.get(
                f"{self._base}/rest/api/1.0/projects/{project_key}/repos",
                params={"limit": 100},
            )
            r.raise_for_status()
            return r.json()

    async def get_file(self, project_key: str, repo_slug: str, file_path: str, branch: str = "main") -> dict[str, Any]:
        async with self._client() as c:
            r = await c.get(
                f"{self._base}/rest/api/1.0/projects/{project_key}/repos/{repo_slug}/raw/{file_path}",
                params={"at": branch},
            )
            r.raise_for_status()
            return {"content": r.text, "file_path": file_path, "branch": branch}

    async def list_prs(self, project_key: str, repo_slug: str, state: str = "OPEN") -> dict[str, Any]:
        async with self._client() as c:
            r = await c.get(
                f"{self._base}/rest/api/1.0/projects/{project_key}/repos/{repo_slug}/pull-requests",
                params={"state": state, "limit": 50},
            )
            r.raise_for_status()
            return r.json()

    async def get_pr_diff(self, project_key: str, repo_slug: str, pr_id: int) -> str:
        async with self._client() as c:
            r = await c.get(
                f"{self._base}/rest/api/1.0/projects/{project_key}/repos/{repo_slug}/pull-requests/{pr_id}/diff",
                headers={**self._headers, "Accept": "text/plain"},
            )
            r.raise_for_status()
            return r.text

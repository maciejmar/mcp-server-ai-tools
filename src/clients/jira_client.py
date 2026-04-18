import httpx
from typing import Any


class JiraClient:
    def __init__(self, base_url: str, token: str, timeout: float = 30.0, ca_bundle: str | None = None):
        self._base = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
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

    async def search(self, jql: str, max_results: int = 20, start_at: int = 0) -> dict[str, Any]:
        async with self._client() as c:
            r = await c.get(
                f"{self._base}/rest/api/2/search",
                params={"jql": jql, "maxResults": max_results, "startAt": start_at,
                        "fields": "summary,status,assignee,priority,description,comment,labels,issuetype"},
            )
            r.raise_for_status()
            return r.json()

    async def get_issue(self, issue_key: str) -> dict[str, Any]:
        async with self._client() as c:
            r = await c.get(
                f"{self._base}/rest/api/2/issue/{issue_key}",
                params={"fields": "summary,status,assignee,priority,description,comment,labels,issuetype,reporter,created,updated"},
            )
            r.raise_for_status()
            return r.json()

    async def create_issue(self, project_key: str, summary: str, description: str, issue_type: str = "Task") -> dict[str, Any]:
        payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": description,
                "issuetype": {"name": issue_type},
            }
        }
        async with self._client() as c:
            r = await c.post(f"{self._base}/rest/api/2/issue", json=payload)
            r.raise_for_status()
            return r.json()

    async def add_comment(self, issue_key: str, comment: str) -> dict[str, Any]:
        async with self._client() as c:
            r = await c.post(
                f"{self._base}/rest/api/2/issue/{issue_key}/comment",
                json={"body": comment},
            )
            r.raise_for_status()
            return r.json()

    async def get_transitions(self, issue_key: str) -> dict[str, Any]:
        async with self._client() as c:
            r = await c.get(f"{self._base}/rest/api/2/issue/{issue_key}/transitions")
            r.raise_for_status()
            return r.json()

    async def transition(self, issue_key: str, transition_id: str) -> None:
        async with self._client() as c:
            r = await c.post(
                f"{self._base}/rest/api/2/issue/{issue_key}/transitions",
                json={"transition": {"id": transition_id}},
            )
            r.raise_for_status()

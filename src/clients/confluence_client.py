import httpx
from typing import Any


class ConfluenceClient:
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

    async def search(self, cql: str, max_results: int = 10) -> dict[str, Any]:
        async with self._client() as c:
            r = await c.get(
                f"{self._base}/rest/api/content/search",
                params={"cql": cql, "limit": max_results, "expand": "space,excerpt"},
            )
            r.raise_for_status()
            return r.json()

    async def get_page(self, page_id: str) -> dict[str, Any]:
        async with self._client() as c:
            r = await c.get(
                f"{self._base}/rest/api/content/{page_id}",
                params={"expand": "body.storage,body.view,version,space,ancestors"},
            )
            r.raise_for_status()
            return r.json()

    async def get_page_version(self, page_id: str) -> int:
        data = await self.get_page(page_id)
        return data["version"]["number"]

    async def create_page(self, space_key: str, title: str, body: str, parent_id: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "body": {
                "storage": {
                    "value": body,
                    "representation": "storage",
                }
            },
        }
        if parent_id:
            payload["ancestors"] = [{"id": parent_id}]

        async with self._client() as c:
            r = await c.post(f"{self._base}/rest/api/content", json=payload)
            r.raise_for_status()
            return r.json()

    async def update_page(self, page_id: str, title: str, body: str) -> dict[str, Any]:
        current_version = await self.get_page_version(page_id)
        payload = {
            "type": "page",
            "title": title,
            "version": {"number": current_version + 1},
            "body": {
                "storage": {
                    "value": body,
                    "representation": "storage",
                }
            },
        }
        async with self._client() as c:
            r = await c.put(f"{self._base}/rest/api/content/{page_id}", json=payload)
            r.raise_for_status()
            return r.json()

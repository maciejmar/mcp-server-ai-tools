import httpx
from typing import Any


class GrafanaClient:
    def __init__(self, base_url: str, token: str, timeout: float = 60.0, ca_bundle: str | None = None):
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

    async def search_dashboards(self, query: str) -> list[dict[str, Any]]:
        async with self._client() as c:
            r = await c.get(
                f"{self._base}/api/search",
                params={"query": query, "type": "dash-db"},
            )
            r.raise_for_status()
            return r.json()

    async def query_datasource(
        self,
        datasource_uid: str,
        query: str,
        from_time: str = "now-1h",
        to_time: str = "now",
    ) -> dict[str, Any]:
        payload = {
            "queries": [
                {
                    "refId": "A",
                    "datasource": {"uid": datasource_uid},
                    "expr": query,
                }
            ],
            "from": from_time,
            "to": to_time,
        }
        async with self._client() as c:
            r = await c.post(f"{self._base}/api/ds/query", json=payload)
            r.raise_for_status()
            return r.json()

    async def get_alerts(self, state: str = "firing") -> list[dict[str, Any]]:
        async with self._client() as c:
            r = await c.get(
                f"{self._base}/api/alertmanager/grafana/api/v2/alerts",
                params={"active": str(state == "firing").lower(),
                        "silenced": "false",
                        "inhibited": "false"},
            )
            r.raise_for_status()
            return r.json()

import httpx
from typing import Any


class OllamaClient:
    def __init__(self, base_url: str, timeout: float = 30.0):
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._timeout)

    async def list_models(self) -> dict[str, Any]:
        async with self._client() as c:
            r = await c.get(f"{self._base}/api/tags")
            r.raise_for_status()
            return r.json()

    async def model_info(self, model_name: str) -> dict[str, Any]:
        async with self._client() as c:
            r = await c.post(f"{self._base}/api/show", json={"name": model_name})
            r.raise_for_status()
            return r.json()

import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Weryfikuje X-API-Key dla wszystkich żądań poza /health."""

    def __init__(self, app, api_key: str):
        super().__init__(app)
        self._api_key = api_key

    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/health", "/"):
            return await call_next(request)

        if not self._api_key:
            logger.warning("MCP_API_KEY not set — skipping auth check")
            return await call_next(request)

        provided = request.headers.get("X-API-Key", "")
        if provided != self._api_key:
            logger.warning(
                "Unauthorized request",
                extra={"path": request.url.path, "client_ip": request.client.host if request.client else "unknown"},
            )
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

        return await call_next(request)

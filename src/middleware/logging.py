import json
import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger("audit")


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    """Loguje każde żądanie w formacie JSON do celów audytu."""

    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()
        client_ip = request.client.host if request.client else "unknown"

        response = await call_next(request)

        elapsed_ms = round((time.monotonic() - start) * 1000, 1)
        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "client_ip": client_ip,
            "elapsed_ms": elapsed_ms,
        }
        logger.info(json.dumps(record, ensure_ascii=False))
        return response


def configure_json_logging(level: str = "INFO") -> None:
    """Konfiguruje root logger do emitowania logów w formacie JSON."""

    class JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            base = {
                "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            extra = {
                k: v
                for k, v in record.__dict__.items()
                if k not in logging.LogRecord.__dict__ and not k.startswith("_")
                and k not in ("msg", "args", "levelname", "levelno", "pathname",
                              "filename", "module", "exc_info", "exc_text",
                              "stack_info", "lineno", "funcName", "created",
                              "msecs", "relativeCreated", "thread", "threadName",
                              "processName", "process", "taskName", "name",
                              "message")
            }
            if extra:
                base.update(extra)
            if record.exc_info:
                base["exception"] = self.formatException(record.exc_info)
            return json.dumps(base, ensure_ascii=False)

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()
    root.addHandler(handler)

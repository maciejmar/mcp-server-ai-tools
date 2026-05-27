import logging
import re
from pathlib import Path
from typing import Iterable

from mcp.server.fastmcp import FastMCP

from src.config import settings

logger = logging.getLogger(__name__)


SENSITIVE_PATTERNS = [
    re.compile(r"(?i)(password|passwd|pwd|secret|token|api[_-]?key)\s*[:=]\s*\S+"),
    re.compile(r"(?i)(authorization:\s*bearer)\s+\S+"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
]

NOISY_LOG_PATTERNS = [
    re.compile(r"\bDEBUG\b", re.IGNORECASE),
    re.compile(r"\bTRACE\b", re.IGNORECASE),
    re.compile(r"health(check)?", re.IGNORECASE),
]

SIGNAL_LOG_PATTERNS = [
    re.compile(r"\b(ERROR|CRITICAL|FATAL|WARN|WARNING)\b", re.IGNORECASE),
    re.compile(r"\b(exception|traceback|failed|timeout|refused|denied|oom|out of memory)\b", re.IGNORECASE),
    re.compile(r"\b(config|configuration|env|missing|required|invalid)\b", re.IGNORECASE),
]


def register_log_tools(mcp: FastMCP) -> None:
    """Register read-only log tools with path allowlisting and redaction."""

    @mcp.tool()
    async def log_list_allowed_paths() -> dict:
        """Lists log paths that this MCP server is allowed to read."""
        paths = [str(path) for path in _allowed_log_paths()]
        return {"count": len(paths), "paths": paths}

    @mcp.tool()
    async def log_read_filtered(path: str | None = None, max_lines: int | None = None) -> dict:
        """Reads high-signal log lines from an allowlisted file.

        The tool removes noisy lines and redacts secrets before returning data.
        It never reads paths outside MCP_ALLOWED_LOG_PATHS.
        """
        logger.info("log_read_filtered called", extra={"tool": "log_read_filtered", "path": path})
        resolved = _resolve_allowed_path(path)
        if resolved is None:
            return {
                "error": "No allowed log file was found",
                "requested_path": path,
                "available_paths": [str(item) for item in _allowed_log_paths()],
                "lines": [],
            }

        limit = _bounded_limit(max_lines)
        raw_lines = _tail_lines(resolved, limit)
        filtered = list(_filter_and_redact(raw_lines))
        return {
            "path": str(resolved),
            "raw_line_count": len(raw_lines),
            "filtered_line_count": len(filtered),
            "lines": filtered,
        }

    @mcp.tool()
    async def log_find_errors(path: str | None = None, max_lines: int | None = None) -> dict:
        """Returns grouped error signals from an allowlisted log file."""
        snapshot = await log_read_filtered(path=path, max_lines=max_lines)
        if snapshot.get("error"):
            return snapshot

        groups = {
            "critical": [],
            "configuration": [],
            "network": [],
            "resource": [],
            "warning": [],
        }
        for line in snapshot.get("lines", []):
            target = _classify_line(line)
            groups[target].append(line)

        return {
            "path": snapshot.get("path"),
            "raw_line_count": snapshot.get("raw_line_count"),
            "filtered_line_count": snapshot.get("filtered_line_count"),
            "groups": {key: value[:20] for key, value in groups.items() if value},
        }


def _allowed_log_paths() -> list[Path]:
    raw_paths = getattr(settings, "MCP_ALLOWED_LOG_PATHS", "")
    return [Path(item.strip()).resolve() for item in raw_paths.split(",") if item.strip()]


def _resolve_allowed_path(requested_path: str | None) -> Path | None:
    allowed = _allowed_log_paths()
    candidates = allowed
    if requested_path:
        requested = Path(requested_path).resolve()
        candidates = [path for path in allowed if path == requested]

    for path in candidates:
        if path.exists() and path.is_file():
            return path
    return None


def _bounded_limit(max_lines: int | None) -> int:
    default_limit = getattr(settings, "MCP_MAX_LOG_LINES", 500)
    hard_limit = getattr(settings, "MCP_MAX_LOG_LINES_HARD_LIMIT", 2000)
    requested = max_lines or default_limit
    return max(1, min(requested, hard_limit))


def _tail_lines(path: Path, limit: int) -> list[str]:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        lines = handle.readlines()
    return [line.rstrip("\n") for line in lines[-limit:]]


def _filter_and_redact(lines: Iterable[str]) -> Iterable[str]:
    for line in lines:
        if any(pattern.search(line) for pattern in NOISY_LOG_PATTERNS):
            continue
        if not any(pattern.search(line) for pattern in SIGNAL_LOG_PATTERNS):
            continue
        yield _redact(line)


def _redact(text: str) -> str:
    redacted = text
    for pattern in SENSITIVE_PATTERNS:
        redacted = pattern.sub(lambda match: _mask_match(match.group(0)), redacted)
    return redacted


def _mask_match(value: str) -> str:
    if ":" in value:
        key = value.split(":", 1)[0]
        return f"{key}: [REDACTED]"
    if "=" in value:
        key = value.split("=", 1)[0]
        return f"{key}=[REDACTED]"
    return "[REDACTED]"


def _classify_line(line: str) -> str:
    if re.search(r"\b(CRITICAL|FATAL|panic|out of memory|oom|startup failed)\b", line, re.IGNORECASE):
        return "critical"
    if re.search(r"config|configuration|\.env|environment variable|missing|required|invalid", line, re.IGNORECASE):
        return "configuration"
    if re.search(r"connection refused|timeout|timed out|dns|network unreachable", line, re.IGNORECASE):
        return "network"
    if re.search(r"no space left|disk full|high cpu|memory usage|too many open files", line, re.IGNORECASE):
        return "resource"
    return "warning"

import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from backend.app.config import Settings
from backend.app.platform.runtime_permissions import (
    RuntimeToolPermissionDenied,
    parse_scoped_user_id,
)


logger = logging.getLogger(__name__)

RUNTIME_AUDIT_MODES = {"runtime_echo", "mock"}


def now_utc_iso() -> str:
    return datetime.now(UTC).isoformat()


def runtime_audit_enabled(settings: Settings) -> bool:
    if not settings.platform_enable_runtime_audit:
        return False
    return settings.platform_runtime_audit_mode.strip().lower() in RUNTIME_AUDIT_MODES


def _jsonl_path(path_value: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = Path.cwd().joinpath(path)
    return path


def write_runtime_tool_audit_record(
    settings: Settings,
    record: dict[str, Any],
) -> None:
    """Write runtime audit to the existing audit and trace JSONL files."""

    written_paths: set[Path] = set()
    for path_value in (
        settings.platform_tool_audit_log_file,
        settings.platform_tool_trace_log_file,
    ):
        path = _jsonl_path(path_value)
        if path in written_paths:
            continue
        written_paths.add(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_runtime_audit_record(
    *,
    trace_id: str,
    scoped_user_id: str,
    agent_id: str,
    session_id: str,
    tool_name: str,
    allowed: bool,
    status: str,
    started_at: str,
    finished_at: str,
    duration_ms: int,
    error_code: str | None,
) -> dict[str, Any]:
    parsed = parse_scoped_user_id(scoped_user_id)
    tenant_id = parsed[0] if parsed else "unknown"
    user_id = parsed[1] if parsed else "unknown"
    return {
        "trace_id": trace_id,
        "event_type": "runtime_tool_call",
        "source": "agentscope_runtime",
        "tenant_id": tenant_id,
        "user_id": user_id,
        "scoped_user_id": scoped_user_id,
        "agent_id": agent_id,
        "session_id": session_id,
        "tool_name": tool_name,
        "allowed": allowed,
        "timestamp": finished_at,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_ms": duration_ms,
        "error_code": error_code,
    }


async def run_runtime_tool_with_audit(
    settings: Settings,
    scoped_user_id: str,
    agent_id: str,
    session_id: str,
    tool_name: str,
    call: Callable[[], Awaitable[Any]],
) -> Any:
    """Run a runtime tool and optionally write a structured audit record."""

    if not runtime_audit_enabled(settings):
        return await call()

    trace_id = uuid4().hex
    started_at = now_utc_iso()
    started = perf_counter()

    async def write_record(
        *,
        allowed: bool,
        status: str,
        error_code: str | None,
    ) -> None:
        finished_at = now_utc_iso()
        duration_ms = int((perf_counter() - started) * 1000)
        record = build_runtime_audit_record(
            trace_id=trace_id,
            scoped_user_id=scoped_user_id,
            agent_id=agent_id,
            session_id=session_id,
            tool_name=tool_name,
            allowed=allowed,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            error_code=error_code,
        )
        try:
            write_runtime_tool_audit_record(settings, record)
        except Exception:  # pylint: disable=broad-except
            logger.exception("Failed to write runtime tool audit record.")

    try:
        result = await call()
    except RuntimeToolPermissionDenied:
        await write_record(
            allowed=False,
            status="denied",
            error_code=RuntimeToolPermissionDenied.error_code,
        )
        raise
    except Exception as exc:
        await write_record(
            allowed=True,
            status="error",
            error_code=type(exc).__name__,
        )
        raise

    await write_record(allowed=True, status="success", error_code=None)
    return result

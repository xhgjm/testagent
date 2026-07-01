import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.app.config import Settings
from backend.app.platform.security import ScopedUser


def _audit_path(settings: Settings) -> Path:
    path = Path(settings.platform_tool_audit_log_file)
    if not path.is_absolute():
        path = Path.cwd().joinpath(path)
    return path


def append_tool_audit_record(
    settings: Settings,
    scoped_user: ScopedUser,
    agent_id: str,
    session_id: str,
    tool_name: str,
    allowed: bool,
) -> dict[str, Any]:
    record = {
        "tenant_id": scoped_user.tenant_id,
        "user_id": scoped_user.user_id,
        "agent_id": agent_id,
        "session_id": session_id,
        "tool_name": tool_name,
        "allowed": allowed,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    path = _audit_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def read_tool_audit_records(
    settings: Settings,
    scoped_user: ScopedUser,
    *,
    agent_id: str | None = None,
    session_id: str | None = None,
    tool_name: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    path = _audit_path(settings)
    if not path.exists():
        return []

    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("tenant_id") != scoped_user.tenant_id:
            continue
        if record.get("user_id") != scoped_user.user_id:
            continue
        if agent_id and record.get("agent_id") != agent_id:
            continue
        if session_id and record.get("session_id") != session_id:
            continue
        if tool_name and record.get("tool_name") != tool_name:
            continue
        records.append(record)
    return records[-limit:]

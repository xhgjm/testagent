from pathlib import Path
from re import sub
from datetime import UTC, datetime
from typing import Any

from backend.app.config import Settings
from backend.app.platform.security import ScopedUser


def safe_path_part(value: str) -> str:
    return sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "unknown"


def resolve_workspace_path(
    settings: Settings,
    scoped_user: ScopedUser,
    agent_id: str,
    session_id: str,
) -> Path:
    """Resolve a tenant/user/agent/session scoped workspace path."""

    base = Path(settings.workspace_basedir).resolve()
    path = base.joinpath(
        safe_path_part(scoped_user.tenant_id),
        safe_path_part(scoped_user.user_id),
        safe_path_part(agent_id),
        safe_path_part(session_id),
    ).resolve()

    if base != path and base not in path.parents:
        raise ValueError("Resolved workspace path escaped the workspace base directory.")
    return path


def ensure_workspace_path(
    settings: Settings,
    scoped_user: ScopedUser,
    agent_id: str,
    session_id: str,
    create: bool,
) -> tuple[Path, bool]:
    path = resolve_workspace_path(settings, scoped_user, agent_id, session_id)
    created = False
    if create and not path.exists():
        path.mkdir(parents=True, exist_ok=True)
        created = True
    return path, created


def list_workspace_files(
    settings: Settings,
    scoped_user: ScopedUser,
    agent_id: str,
    session_id: str,
) -> tuple[Path, list[dict[str, Any]]]:
    workspace = resolve_workspace_path(settings, scoped_user, agent_id, session_id)
    if not workspace.exists():
        return workspace, []

    files: list[dict[str, Any]] = []
    for item in workspace.rglob("*"):
        resolved = item.resolve()
        if workspace != resolved and workspace not in resolved.parents:
            continue
        stat = item.stat()
        files.append(
            {
                "path": item.relative_to(workspace).as_posix(),
                "size_bytes": 0 if item.is_dir() else stat.st_size,
                "modified_at": datetime.fromtimestamp(
                    stat.st_mtime,
                    tz=UTC,
                ).isoformat(),
                "is_dir": item.is_dir(),
            },
        )
    return workspace, files


def cleanup_workspace_candidates(
    settings: Settings,
    scoped_user: ScopedUser,
    agent_id: str,
    session_id: str,
    max_age_days: float,
    dry_run: bool,
) -> tuple[Path, list[dict[str, Any]], int]:
    workspace = resolve_workspace_path(settings, scoped_user, agent_id, session_id)
    if not workspace.exists():
        return workspace, [], 0

    now = datetime.now(UTC)
    candidates: list[dict[str, Any]] = []
    deleted = 0
    for item in workspace.rglob("*"):
        resolved = item.resolve()
        if item.is_dir():
            continue
        if workspace != resolved and workspace not in resolved.parents:
            continue
        stat = item.stat()
        modified = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
        age_days = (now - modified).total_seconds() / 86400
        if age_days < max_age_days:
            continue

        was_deleted = False
        if not dry_run:
            item.unlink()
            was_deleted = True
            deleted += 1
        candidates.append(
            {
                "path": item.relative_to(workspace).as_posix(),
                "size_bytes": stat.st_size,
                "modified_at": modified.isoformat(),
                "age_days": round(age_days, 4),
                "deleted": was_deleted,
            },
        )

    if not dry_run:
        for item in sorted(workspace.rglob("*"), key=lambda path: len(path.parts), reverse=True):
            if item.is_dir():
                try:
                    item.rmdir()
                except OSError:
                    pass

    return workspace, candidates, deleted

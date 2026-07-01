from pathlib import Path
from re import sub

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

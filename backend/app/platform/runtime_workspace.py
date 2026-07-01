import logging
from dataclasses import dataclass

from backend.app.config import Settings
from backend.app.platform.runtime_permissions import parse_scoped_user_id
from backend.app.platform.security import ScopedUser
from backend.app.platform.workspace import ensure_workspace_path


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuntimeWorkspaceContext:
    tenant_id: str
    user_id: str
    scoped_user_id: str
    agent_id: str
    session_id: str
    workspace_path: str
    exists: bool
    created: bool
    isolation_strategy: str = "tenant_id/user_id/agent_id/session_id"


def resolve_runtime_workspace(
    settings: Settings,
    scoped_user_id: str,
    agent_id: str,
    session_id: str,
    *,
    create: bool = True,
) -> RuntimeWorkspaceContext | None:
    """Resolve runtime workspace context using the platform workspace rules."""

    parsed_user = parse_scoped_user_id(scoped_user_id)
    if parsed_user is None:
        logger.warning(
            "Runtime workspace requires scoped user id tenant_id:user_id; got %r.",
            scoped_user_id,
        )
        return None

    tenant_id, user_id = parsed_user
    scoped_user = ScopedUser(
        tenant_id=tenant_id,
        user_id=user_id,
        scoped_user_id=scoped_user_id,
    )

    path, created = ensure_workspace_path(
        settings,
        scoped_user,
        agent_id,
        session_id,
        create=create,
    )

    return RuntimeWorkspaceContext(
        tenant_id=tenant_id,
        user_id=user_id,
        scoped_user_id=scoped_user_id,
        agent_id=agent_id,
        session_id=session_id,
        workspace_path=str(path),
        exists=path.exists(),
        created=created,
    )

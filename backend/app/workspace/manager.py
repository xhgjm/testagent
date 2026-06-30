from pathlib import Path
from re import sub

from pydantic import BaseModel

from backend.app.config import Settings
from backend.app.platform_context import PlatformContext


class WorkspacePlan(BaseModel):
    backend: str
    base_dir: str
    path: str
    ttl_seconds: int
    isolation_strategy: str


def _safe_part(value: str) -> str:
    return sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "unknown"


def build_workspace_plan(
    settings: Settings,
    context: PlatformContext,
    enterprise_mode: bool = True,
) -> WorkspacePlan:
    """Return a workspace plan without creating files.

    Development strategy:
    - user_id + agent_id

    Enterprise strategy:
    - tenant_id + user_id + agent_id + session_id

    TODO: Connect AgentScope LocalWorkspaceManager for local execution.
    TODO: Connect AgentScope DockerWorkspaceManager or E2B for isolated execution.
    """

    parts = [_safe_part(part) for part in context.isolation_parts(enterprise_mode)]
    path = Path(settings.workspace_basedir).joinpath(*parts)
    strategy = (
        "tenant_id/user_id/agent_id/session_id"
        if enterprise_mode
        else "user_id/agent_id"
    )
    return WorkspacePlan(
        backend=settings.workspace_backend,
        base_dir=settings.workspace_basedir,
        path=str(path),
        ttl_seconds=settings.workspace_ttl_seconds,
        isolation_strategy=strategy,
    )

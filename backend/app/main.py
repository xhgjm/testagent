from fastapi import Depends, FastAPI

from backend.app.auth.current_user import CurrentUser, get_current_user
from backend.app.config import Settings, get_settings
from backend.app.memory.config import build_memory_plan
from backend.app.middlewares.factory import build_extra_agent_middlewares
from backend.app.platform_context import PlatformContext
from backend.app.rag.config import build_rag_service_plan
from backend.app.team.config import build_agent_team_plan
from backend.app.tools.factory import build_extra_agent_tools
from backend.app.workspace.manager import build_workspace_plan


def create_platform_app(settings: Settings | None = None) -> FastAPI:
    """Create the enterprise platform FastAPI app.

    TODO: Confirm the exact AgentScope 2.0.3 Agent Service import path before
    replacing or mounting this app with the official create_app entry point.

    Intended integration shape:
    - load settings
    - initialize storage, later RedisStorage
    - initialize message_bus, later RedisMessageBus
    - initialize workspace_manager, later LocalWorkspaceManager or DockerWorkspaceManager
    - register extra_agent_tools factory
    - register extra_agent_middlewares factory
    - reserve knowledge_base_manager, blob_store, parsers, chunker
    - return FastAPI app
    """

    settings = settings or get_settings()
    app = FastAPI(
        title="AgentScope Enterprise Multi-Tenant Agent Platform",
        description="MVP scaffold for an enterprise AgentScope 2.0.3 platform.",
        version="0.1.0",
    )
    app.state.settings = settings

    # TODO: Initialize AgentScope storage here after confirming 2.0.3 import path.
    app.state.storage = None
    # TODO: Initialize AgentScope RedisMessageBus here.
    app.state.message_bus = None
    # TODO: Initialize AgentScope workspace manager here.
    app.state.workspace_manager = None
    # TODO: Initialize RAG knowledge_base_manager, blob_store, parsers, chunker.
    app.state.knowledge_base_manager = None

    @app.get("/health", tags=["platform"])
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "app": settings.app_name,
            "env": settings.app_env,
        }

    @app.get("/api/me", tags=["platform"])
    async def read_current_user(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> dict[str, object]:
        return current_user.model_dump()

    @app.get("/api/platform/capabilities", tags=["platform"])
    async def read_platform_capabilities(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> dict[str, object]:
        context = PlatformContext(
            tenant_id=current_user.tenant_id,
            user_id=current_user.user_id,
            role=current_user.role,
            permissions=current_user.permissions,
        )
        return {
            "identity_mode": "header_simulation",
            "agentscope_agent_service": "TODO: mount official Agent Service app",
            "storage": "TODO: RedisStorage",
            "message_bus": "TODO: RedisMessageBus",
            "workspace": build_workspace_plan(settings, context).model_dump(),
            "extra_agent_tools": len(build_extra_agent_tools(context)),
            "extra_agent_middlewares": len(build_extra_agent_middlewares(context)),
            "rag": build_rag_service_plan(settings).model_dump(),
            "memory": build_memory_plan().model_dump(),
            "team": build_agent_team_plan().model_dump(),
        }

    return app


app = create_platform_app()

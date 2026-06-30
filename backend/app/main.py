from fastapi import APIRouter, Depends, FastAPI

from agentscope.app import create_app as create_agentscope_app
from agentscope.app.message_bus import RedisMessageBus
from agentscope.app.storage import RedisStorage
from agentscope.app.workspace_manager import LocalWorkspaceManager

from backend.app.auth.current_user import CurrentUser, get_current_user
from backend.app.config import Settings, get_settings
from backend.app.memory.config import build_memory_plan
from backend.app.middlewares.factory import build_extra_agent_middlewares
from backend.app.platform_context import PlatformContext
from backend.app.rag.config import build_rag_service_plan
from backend.app.team.config import build_agent_team_plan
from backend.app.tools.factory import build_extra_agent_tools
from backend.app.workspace.manager import build_workspace_plan


def create_platform_router(settings: Settings) -> APIRouter:
    """Create platform-owned routes mounted onto the AgentScope app."""

    router = APIRouter(tags=["platform"])

    @router.get("/platform/health")
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "app": settings.app_name,
            "env": settings.app_env,
            "agent_service": "agentscope",
        }

    @router.get("/api/me")
    async def read_current_user(
        current_user: CurrentUser = Depends(get_current_user),
    ) -> dict[str, object]:
        return current_user.model_dump()

    @router.get("/api/platform/capabilities")
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
            "agentscope_agent_service": "enabled",
            "storage": "RedisStorage",
            "message_bus": "RedisMessageBus",
            "workspace": build_workspace_plan(settings, context).model_dump(),
            "extra_agent_tools": len(build_extra_agent_tools(context)),
            "extra_agent_middlewares": len(build_extra_agent_middlewares(context)),
            "rag": build_rag_service_plan(settings).model_dump(),
            "memory": build_memory_plan().model_dump(),
            "team": build_agent_team_plan().model_dump(),
        }

    return router


def create_platform_app(settings: Settings | None = None) -> FastAPI:
    """Create the AgentScope Agent Service app with platform extensions.

    The returned object is the FastAPI app produced by AgentScope 2.0.3
    `create_app`. Platform-specific routes are added with `include_router`,
    so the Agent Service app is not nested under another FastAPI app.
    """

    settings = settings or get_settings()

    storage = RedisStorage(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
    )
    message_bus = RedisMessageBus(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
    )
    workspace_manager = LocalWorkspaceManager(
        basedir=settings.workspace_basedir,
        ttl=float(settings.workspace_ttl_seconds),
    )

    # Phase 1 passes empty extension lists through the existing factories.
    # TODO: Upgrade to tenant/session-aware dynamic injection once the AgentScope
    # extension calling convention is validated in the ECS 2.0.3 environment.
    platform_context = PlatformContext()
    extra_agent_tools = build_extra_agent_tools(platform_context)
    extra_agent_middlewares = build_extra_agent_middlewares(platform_context)

    app = create_agentscope_app(
        storage=storage,
        message_bus=message_bus,
        workspace_manager=workspace_manager,
        knowledge_base_manager=None,
        knowledge_parsers=None,
        knowledge_chunker=None,
        blob_store=None,
        enable_index_worker=True,
        extra_agent_tools=extra_agent_tools,
        extra_agent_middlewares=extra_agent_middlewares,
        title="AgentScope Enterprise Agent Platform",
        version="0.1.0",
    )

    app.state.settings = settings
    app.state.storage = storage
    app.state.message_bus = message_bus
    app.state.workspace_manager = workspace_manager
    # TODO: Wire RAG Service objects: knowledge_base_manager, parsers, chunker,
    # blob_store, and index worker.
    app.state.knowledge_base_manager = None
    # TODO: Wire Long-term Memory and Agent Team after the Agent Service main
    # chain is validated.

    app.include_router(create_platform_router(settings))
    return app


app = create_platform_app()

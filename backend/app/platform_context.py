from pydantic import BaseModel, Field


class PlatformContext(BaseModel):
    """Tenant-aware runtime context passed into tools, middleware, and workspace."""

    tenant_id: str = Field(default="default_tenant")
    user_id: str = Field(default="default_user")
    agent_id: str | None = None
    session_id: str | None = None
    role: str = "user"
    permissions: list[str] = Field(default_factory=list)

    def isolation_parts(self, enterprise_mode: bool = False) -> list[str]:
        """Return logical isolation parts for workspace and resource scoping."""

        if enterprise_mode:
            return [
                self.tenant_id,
                self.user_id,
                self.agent_id or "agent_unbound",
                self.session_id or "session_unbound",
            ]
        return [self.user_id, self.agent_id or "agent_unbound"]

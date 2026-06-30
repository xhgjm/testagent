from fastapi import Header
from pydantic import BaseModel, Field


class CurrentUser(BaseModel):
    """Temporary user model for MVP identity simulation."""

    tenant_id: str = "default_tenant"
    user_id: str = "default_user"
    role: str = "user"
    permissions: list[str] = Field(default_factory=list)


async def get_current_user(
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
) -> CurrentUser:
    """Read MVP identity from headers.

    TODO: Replace this with JWT / OAuth / enterprise SSO.
    TODO: Load tenant_id, role, and permissions from an IAM service or platform DB.
    """

    return CurrentUser(
        tenant_id=x_tenant_id or "default_tenant",
        user_id=x_user_id or "default_user",
        role=x_user_role or "user",
        permissions=[],
    )

from fastapi import Header, HTTPException, status
from pydantic import BaseModel


class ScopedUser(BaseModel):
    tenant_id: str
    user_id: str
    scoped_user_id: str


def build_scoped_user_id(tenant_id: str, user_id: str) -> str:
    """Build the AgentScope user id used for tenant-aware isolation."""

    tenant = tenant_id.strip()
    user = user_id.strip()
    if not tenant or not user:
        raise ValueError("tenant_id and user_id are required")
    return f"{tenant}:{user}"


async def get_scoped_user(
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-ID"),
    x_user_id: str | None = Header(default=None, alias="X-User-ID"),
) -> ScopedUser:
    """Require tenant and user headers for platform facade APIs."""

    if not x_tenant_id or not x_tenant_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Tenant-ID is required for platform APIs.",
        )
    if not x_user_id or not x_user_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-User-ID is required for platform APIs.",
        )

    tenant_id = x_tenant_id.strip()
    user_id = x_user_id.strip()
    return ScopedUser(
        tenant_id=tenant_id,
        user_id=user_id,
        scoped_user_id=build_scoped_user_id(tenant_id, user_id),
    )

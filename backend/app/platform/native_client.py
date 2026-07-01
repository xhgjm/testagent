import re
from typing import Any

import httpx
from fastapi import HTTPException

from backend.app.config import Settings
from backend.app.platform.security import ScopedUser


SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "access_token",
    "refresh_token",
    "token",
    "secret",
    "password",
}


def sanitize_sensitive_data(data: Any) -> Any:
    """Redact sensitive values before returning errors to API callers."""

    if isinstance(data, dict):
        sanitized: dict[Any, Any] = {}
        for key, value in data.items():
            key_text = str(key).lower()
            if key_text in SENSITIVE_KEYS or any(
                marker in key_text for marker in ("api_key", "token", "secret")
            ):
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = sanitize_sensitive_data(value)
        return sanitized
    if isinstance(data, list):
        return [sanitize_sensitive_data(item) for item in data]
    if isinstance(data, str):
        return re.sub(r"sk-[A-Za-z0-9_\-]+", "sk-***REDACTED***", data)
    return data


def extract_resource_id(data: Any, *candidate_keys: str) -> str | None:
    """Extract ids from common AgentScope response shapes."""

    if not isinstance(data, dict):
        return None
    for key in candidate_keys:
        value = data.get(key)
        if value:
            return str(value)
    nested = data.get("data")
    if isinstance(nested, dict):
        for key in candidate_keys:
            value = nested.get(key)
            if value:
                return str(value)
    return None


def extract_collection(data: Any, preferred_key: str) -> tuple[Any, int | None]:
    """Extract list-like results while tolerating native response variations."""

    if isinstance(data, list):
        return data, len(data)
    if isinstance(data, dict):
        for key in (preferred_key, "data", "items", "results"):
            value = data.get(key)
            if isinstance(value, list):
                return value, len(value)
        total = data.get("total")
        return data, total if isinstance(total, int) else None
    return data, None


class AgentScopeNativeClient:
    """Small internal client for calling AgentScope native endpoints."""

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.agent_service_internal_base_url.rstrip("/")

    def _headers(self, scoped_user: ScopedUser) -> dict[str, str]:
        return {
            "X-User-ID": scoped_user.scoped_user_id,
            "X-Tenant-ID": scoped_user.tenant_id,
        }

    async def _request(
        self,
        method: str,
        path: str,
        scoped_user: ScopedUser,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=60.0,
            follow_redirects=True,
        ) as client:
            response = await client.request(
                method,
                path,
                headers=self._headers(scoped_user),
                json=json_body,
                params=params,
            )

        if 200 <= response.status_code < 300:
            if not response.content:
                return {}
            try:
                return sanitize_sensitive_data(response.json())
            except ValueError:
                return {"text": sanitize_sensitive_data(response.text)}

        try:
            detail = response.json()
        except ValueError:
            detail = {"error": response.text}
        raise HTTPException(
            status_code=response.status_code,
            detail=sanitize_sensitive_data(detail),
        )

    async def create_credential(
        self,
        scoped_user: ScopedUser,
        payload: dict[str, Any],
    ) -> Any:
        return await self._request("POST", "/credential/", scoped_user, json_body=payload)

    async def list_agents(self, scoped_user: ScopedUser) -> Any:
        return await self._request("GET", "/agent/", scoped_user)

    async def create_agent(
        self,
        scoped_user: ScopedUser,
        payload: dict[str, Any],
    ) -> Any:
        return await self._request("POST", "/agent/", scoped_user, json_body=payload)

    async def list_sessions(self, scoped_user: ScopedUser, agent_id: str) -> Any:
        return await self._request(
            "GET",
            "/sessions/",
            scoped_user,
            params={"agent_id": agent_id},
        )

    async def create_session(
        self,
        scoped_user: ScopedUser,
        payload: dict[str, Any],
    ) -> Any:
        return await self._request("POST", "/sessions/", scoped_user, json_body=payload)

    async def post_chat(
        self,
        scoped_user: ScopedUser,
        payload: dict[str, Any],
    ) -> Any:
        return await self._request("POST", "/chat/", scoped_user, json_body=payload)

    async def get_messages(
        self,
        scoped_user: ScopedUser,
        session_id: str,
        agent_id: str,
    ) -> Any:
        return await self._request(
            "GET",
            f"/sessions/{session_id}/messages",
            scoped_user,
            params={"agent_id": agent_id},
        )

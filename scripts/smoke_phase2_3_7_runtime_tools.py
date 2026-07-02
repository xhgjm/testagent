import asyncio
import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import Settings
from backend.app.platform.audit import read_tool_audit_records
from backend.app.platform.runtime_permissions import RuntimeToolPermissionDenied
from backend.app.platform.runtime_tools import (
    _build_extra_agent_tools,
    make_runtime_echo_callable,
)
from backend.app.platform.runtime_workspace import resolve_runtime_workspace
from backend.app.platform.security import ScopedUser


TENANT_ID = "smokeTenant"
USER_ID = "smokeUser"
SCOPED_USER_ID = f"{TENANT_ID}:{USER_ID}"
AGENT_ID = "smokeAgent"
SESSION_ID = "smokeSession"
TOOL_NAME = "runtime_echo_tool"
SENSITIVE_TEXT = "phase-237-sensitive-input"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def write_permission_file(path: Path, allow: bool) -> None:
    rules = []
    if allow:
        rules.append(
            {
                "tenant_id": TENANT_ID,
                "user_id": USER_ID,
                "agent_id": AGENT_ID,
                "tool_name": TOOL_NAME,
            },
        )
    path.write_text(
        json.dumps({"allow": rules}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def make_settings(root: Path, *, enabled: bool, audit: bool) -> Settings:
    return Settings(
        workspace_basedir=str(root / "workspaces"),
        platform_tool_permission_file=str(root / "permissions.json"),
        platform_tool_audit_log_file=str(root / "audit.jsonl"),
        platform_tool_trace_log_file=str(root / "trace.jsonl"),
        platform_enable_runtime_tools=enabled,
        platform_runtime_tools_mode="mock" if enabled else "disabled",
        platform_enable_runtime_audit=audit,
        platform_runtime_audit_mode="runtime_echo" if audit else "disabled",
    )


async def run_smoke() -> None:
    smoke_root = PROJECT_ROOT / ".cache" / "agent-platform-smoke"
    smoke_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="phase237-",
        dir=smoke_root,
        ignore_cleanup_errors=True,
    ) as tmp:
        root = Path(tmp)
        permission_file = root / "permissions.json"

        disabled_settings = make_settings(root, enabled=False, audit=False)
        tools = await _build_extra_agent_tools(
            disabled_settings,
            SCOPED_USER_ID,
            AGENT_ID,
            SESSION_ID,
        )
        assert_true(tools == [], "default disabled adapter must return []")

        enabled_settings = make_settings(root, enabled=True, audit=True)
        write_permission_file(permission_file, allow=False)
        tools = await _build_extra_agent_tools(
            enabled_settings,
            SCOPED_USER_ID,
            AGENT_ID,
            SESSION_ID,
        )
        assert_true(tools == [], "enabled adapter without allow must return []")

        write_permission_file(permission_file, allow=True)
        tools = await _build_extra_agent_tools(
            enabled_settings,
            SCOPED_USER_ID,
            AGENT_ID,
            SESSION_ID,
        )
        tool_names = [getattr(tool, "name", "") for tool in tools]
        assert_true(
            tool_names == [TOOL_NAME],
            f"enabled adapter with allow must return {TOOL_NAME}",
        )

        workspace_context = resolve_runtime_workspace(
            enabled_settings,
            SCOPED_USER_ID,
            AGENT_ID,
            SESSION_ID,
            create=True,
        )
        assert_true(workspace_context is not None, "workspace context is required")
        workspace_path = workspace_context.workspace_path
        for value in (TENANT_ID, USER_ID, AGENT_ID, SESSION_ID):
            assert_true(
                value in workspace_path,
                f"workspace path must include {value}",
            )
        assert_true(
            workspace_context.isolation_strategy
            == "tenant_id/user_id/agent_id/session_id",
            "workspace isolation strategy mismatch",
        )

        runtime_echo = make_runtime_echo_callable(
            enabled_settings,
            SCOPED_USER_ID,
            AGENT_ID,
            SESSION_ID,
            workspace_context,
        )
        result = await runtime_echo(SENSITIVE_TEXT)
        assert_true(
            result == {"text": SENSITIVE_TEXT},
            "runtime echo success result mismatch",
        )

        write_permission_file(permission_file, allow=False)
        denied = False
        try:
            await runtime_echo(SENSITIVE_TEXT)
        except RuntimeToolPermissionDenied as exc:
            denied = exc.error_code == "RUNTIME_PERMISSION_DENIED"
        assert_true(denied, "same callable must deny after allow removal")

        audit_path = root / "audit.jsonl"
        records = [
            json.loads(line)
            for line in audit_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert_true(len(records) == 2, "expected success and denied audit records")
        statuses = [record.get("status") for record in records]
        assert_true(statuses == ["success", "denied"], "audit status mismatch")
        assert_true(records[0].get("allowed") is True, "success audit allowed mismatch")
        assert_true(records[1].get("allowed") is False, "denied audit allowed mismatch")
        assert_true(
            records[1].get("error_code") == "RUNTIME_PERMISSION_DENIED",
            "denied audit error_code mismatch",
        )
        for record in records:
            assert_true(record.get("trace_id"), "audit trace_id is required")
            assert_true(
                record.get("duration_ms") is not None,
                "audit duration_ms is required",
            )
            assert_true(
                record.get("workspace_path"),
                "audit workspace_path is required",
            )
            assert_true(
                record.get("workspace_isolation_strategy")
                == "tenant_id/user_id/agent_id/session_id",
                "audit workspace isolation strategy mismatch",
            )
        assert_true(
            SENSITIVE_TEXT not in json.dumps(records, ensure_ascii=False),
            "audit records must not include input text",
        )

        tenant_b_context = resolve_runtime_workspace(
            enabled_settings,
            "tenantB:smokeUser",
            AGENT_ID,
            SESSION_ID,
            create=True,
        )
        assert_true(
            tenant_b_context is not None,
            "tenantB workspace context is required",
        )
        assert_true(
            tenant_b_context.workspace_path != workspace_path,
            "tenantB workspace path must differ from tenantA path",
        )
        assert_true(
            "tenantB" in tenant_b_context.workspace_path,
            "tenantB workspace path must include tenantB",
        )

        tenant_b_records = read_tool_audit_records(
            enabled_settings,
            ScopedUser(
                tenant_id="tenantB",
                user_id=USER_ID,
                scoped_user_id="tenantB:smokeUser",
            ),
        )
        assert_true(tenant_b_records == [], "tenantB must not see tenantA audit")

    print("Phase 2.3.7 runtime tool smoke passed.")


if __name__ == "__main__":
    asyncio.run(run_smoke())

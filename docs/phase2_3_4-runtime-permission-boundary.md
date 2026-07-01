# Phase 2.3.4: Runtime Permission Boundary

## Goal

Phase 2.3.4 adds a minimal runtime permission boundary on top of the Phase 2.3.3 `extra_agent_tools` adapter skeleton.

This phase still keeps runtime tools disabled by default. It does not connect MCP, Skills, real enterprise tools, shell commands, system commands, file deletion, network access, RAG, Memory, Team, or frontend.

## Why Injection-Time Filtering Is Not Enough

Phase 2.3.3 only filtered tools before injection:

- no allow rule means no runtime tool is injected
- allow rule means `runtime_echo_tool` can be injected in explicit mock mode

That is useful, but insufficient. A tool can be injected while permission exists, then the allow rule can be deleted before the tool is actually called. Without an execution-time check, that already-constructed callable could still run.

Phase 2.3.4 adds the second boundary:

- first layer: injection-time filtering
- second layer: execution-time permission check inside the runtime tool callable

## Implemented Modules

New module:

```text
backend/app/platform/runtime_permissions.py
```

Responsibilities:

- parse AgentScope runtime `user_id` in the platform format `tenant_id:user_id`
- reuse existing platform permission JSON as the enterprise permission source
- provide runtime allow/deny helpers
- raise a clear `RuntimeToolPermissionDenied` exception
- provide an experimental AgentScope `PermissionRule` mapper helper

## Runtime Permission API

Key helpers:

```python
parse_scoped_user_id(scoped_user_id: str) -> tuple[str, str] | None
```

```python
is_runtime_tool_allowed(
    scoped_user_id: str,
    agent_id: str,
    session_id: str,
    tool_name: str,
    *,
    settings: Settings | None = None,
) -> bool
```

```python
ensure_runtime_tool_allowed(...) -> None
```

`ensure_runtime_tool_allowed` raises:

```python
RuntimeToolPermissionDenied
```

The exception has:

```text
error_code = "RUNTIME_PERMISSION_DENIED"
```

Current permission granularity remains:

- `tenant_id`
- `user_id`
- `agent_id`
- `tool_name`

`session_id` is accepted for runtime context and future audit/tracing, but current JSON rules do not yet use it.

## Platform Permission JSON As Enterprise Source

The existing permission JSON remains the enterprise policy source:

```json
{
  "allow": [
    {
      "tenant_id": "tenantA",
      "user_id": "userA",
      "agent_id": "agentSmoke",
      "tool_name": "runtime_echo_tool"
    }
  ]
}
```

Default deny remains unchanged. Invalid scoped user ids also deny.

## runtime_echo_tool Execution Boundary

`runtime_echo_tool` is now built from a closure that binds:

- `scoped_user_id`
- `agent_id`
- `session_id`
- `tool_name`
- `settings`

Before returning text, the callable runs:

```python
ensure_runtime_tool_allowed(...)
```

This means:

- allow exists at injection time: tool can be injected
- allow is deleted after injection: the same tool callable is denied at execution time

The tool still only echoes text. It does not access files, network, commands, environment variables, or enterprise systems.

## AgentScope PermissionRule Mapper

Phase 2.3.4 adds an experimental helper:

```python
build_agentscope_permission_rule_for_tool(
    tool_name: str,
    *,
    effect: Literal["allow", "deny", "ask"] = "allow",
    rule_content: str | None = None,
    source: str = "agent-platform",
) -> PermissionRule | None
```

It uses verified AgentScope imports:

```python
from agentscope.permission import PermissionBehavior, PermissionRule
```

Mapping:

- `allow` -> `PermissionBehavior.ALLOW`
- `deny` -> `PermissionBehavior.DENY`
- `ask` -> `PermissionBehavior.ASK`

This helper is not wired into AgentScope `PermissionContext` yet. It is only a safe mapper building block for later phases.

## What Is Not Connected To PermissionContext

This phase does not modify AgentScope default permission behavior.

Not connected yet:

- `PermissionContext.allow_rules`
- `PermissionContext.deny_rules`
- `PermissionContext.ask_rules`
- ASK-mode enterprise approval workflow
- runtime audit middleware

AgentScope `FunctionTool.check_permissions` may still default to ASK internally. The platform execution-time check is a separate safety boundary for the experimental runtime echo tool.

## Why MCP And Skills Are Not Enabled

MCP and Skills require more governance:

- parameter schema review
- tenant/user/agent permission policy
- timeout controls
- workspace boundaries
- secret handling
- runtime audit/tracing
- lifecycle management

They remain disabled in this phase.

## Why Runtime Audit JSONL Is Not Implemented

This phase focuses only on permission boundaries. Runtime audit/tracing JSONL belongs to Phase 2.3.5, likely through `extra_agent_middlewares` and `MiddlewareBase.on_acting`.

The existing platform invoke audit remains unchanged.

## Relationship To Phase 2.3.3

Phase 2.3.3 introduced:

- default-closed runtime adapter skeleton
- `runtime_echo_tool`
- injection-time permission filtering

Phase 2.3.4 adds:

- execution-time permission checking
- `RuntimeToolPermissionDenied`
- experimental `PermissionRule` mapper helper

## Relationship To Phase 2.3.5

Phase 2.3.5 adds runtime audit/tracing for `runtime_echo_tool`:

- trace id
- runtime tool name
- allowed/denied/error status
- started/finished timestamps
- duration
- error code

This does not replace the permission checks added here. It wraps the same runtime callable and records success/denied/error outcomes without logging user input text.

## Local Smoke Test

### A. Default Closed

```powershell
conda run -n agent-platform python -c "import asyncio; from backend.app.tools.factory import build_extra_agent_tools; print(asyncio.run(build_extra_agent_tools('tenantA:userA','agentSmoke','sessionSmoke')))"
```

Expected:

```text
[]
```

### B. Enabled Without Allow

```powershell
conda run -n agent-platform python -c "import asyncio; from backend.app.config import Settings; from backend.app.platform.runtime_tools import _build_extra_agent_tools; s=Settings(platform_enable_runtime_tools=True, platform_runtime_tools_mode='mock', platform_tool_permission_file='tmp/missing-runtime-permissions.json'); print(asyncio.run(_build_extra_agent_tools(s, 'tenantA:userA', 'agentSmoke', 'sessionSmoke')))"
```

Expected:

```text
[]
```

### C. Enabled With Allow

Create a temporary permission file with an allow rule for `runtime_echo_tool`, then call the adapter.

Expected:

```text
['runtime_echo_tool']
```

### D. Execution-Time Deny After Rule Deletion

Smoke design:

1. Build `runtime_echo_tool` while allow exists.
2. Call the tool once: should succeed.
3. Delete the allow rule.
4. Call the same constructed tool again without rebuilding it.
5. Expected: `RuntimeToolPermissionDenied` with `RUNTIME_PERMISSION_DENIED`.

This proves the runtime tool checks permission at execution time, not only during injection.

### E. Platform Invoke API Regression

The existing platform invoke APIs are unchanged:

- `POST /api/platform/tools/echo_tool/invoke`
- `POST /api/platform/tools/slow_tool/invoke`
- `GET /api/platform/audit/tool-calls`

They should continue to use Phase 2.1 permission, timeout, audit, and tracing behavior.

## ECS Smoke Test

After commit and push:

```bash
cd /app/agent-platform
git pull
source .venv/bin/activate
python -m compileall backend/app
```

Confirm runtime tools remain disabled by default in `.env`:

```env
PLATFORM_ENABLE_RUNTIME_TOOLS=false
PLATFORM_RUNTIME_TOOLS_MODE=disabled
```

Restart the backend on port `8891` and verify Phase 1.5 chat/session/message still works.

Then run isolated Python checks for:

- no allow -> adapter returns `[]`
- allow -> adapter returns `runtime_echo_tool`
- delete allow -> same callable rejects with `RUNTIME_PERMISSION_DENIED`

Do not require the model to automatically call `runtime_echo_tool` in real chat during this phase.

## Risks And Limits

- This is not full AgentScope `PermissionContext` integration.
- Runtime audit/tracing JSONL is not implemented yet.
- Platform permission JSON is still not production-grade concurrent storage.
- Invalid or unscoped AgentScope `user_id` values deny runtime tool access.
- MCP and Skills remain disabled.
- No shell, system command, file delete, network, or enterprise-system tools are enabled.
- ASK mode remains disabled for enterprise platform usage.

## Next Step: Phase 2.3.5

Phase 2.3.5 follow-up:

- `runtime_echo_tool` audit/tracing is implemented.
- `extra_agent_middlewares` skeleton is connected through the existing factory and remains disabled by default.
- Full details: [phase2_3_5-runtime-audit-middleware.md](phase2_3_5-runtime-audit-middleware.md).


## ECS Smoke Test Result

Date: 2026-07-01
Port: 8891
Result: Passed

Verified:
- Default configuration keeps runtime tools disabled.
- build_extra_agent_tools returns [] by default.
- Existing chat/session/message flow still works with runtime tools disabled.
- With explicit runtime enablement and permission allow, adapter returns runtime_echo_tool.
- runtime_echo_tool performs execution-time permission re-check.
- After deleting the allow rule, the already constructed runtime callable refuses execution with RuntimeToolPermissionDenied.
- The expected error_code is RUNTIME_PERMISSION_DENIED.
- Test runtime_echo_tool allow rules were cleaned up after the smoke test.
- No MCP, Skill, shell, file deletion, network access, or enterprise system integration is enabled.

Evidence:
- FIRST_CALL_OK {'text': 'first call should pass'}
- SECOND_CALL_DENIED
- ERROR_CODE RUNTIME_PERMISSION_DENIED

Conclusion:
Phase 2.3.4 runtime permission boundary passed ECS smoke test.

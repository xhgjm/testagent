# Phase 2.3.5: Runtime Tool Audit / Tracing Middleware

## Goal

Phase 2.3.5 adds minimal runtime audit/tracing for AgentScope runtime tool calling. The concrete coverage in this phase is the safe mock `runtime_echo_tool`.

This phase keeps runtime tools and runtime audit disabled by default. It does not enable MCP, Skills, real enterprise tools, shell commands, system commands, file deletion, network access, RAG, Memory, Team, or frontend.

## Why Phase 2.3.4 Was Not Enough

Phase 2.3.4 added a runtime permission boundary:

- injection-time allow filtering
- execution-time permission check

That proved the runtime tool can be denied after an allow rule is deleted. It did not record runtime success or denied attempts into audit JSONL. Phase 2.3.5 adds structured records so runtime tool calls can be observed separately from platform invoke calls.

## New Modules

```text
backend/app/platform/runtime_audit.py
backend/app/platform/runtime_middlewares.py
```

`runtime_audit.py` writes records for `runtime_echo_tool` through a callable wrapper.

`runtime_middlewares.py` provides a minimal `MiddlewareBase` skeleton for future generic runtime acting/tool event tracing. It is connected through `backend/app/middlewares/factory.py`, but default configuration returns `[]`.

## Configuration

`.env.example` includes:

```env
PLATFORM_ENABLE_RUNTIME_AUDIT=false
PLATFORM_RUNTIME_AUDIT_MODE=disabled
```

Supported experimental modes:

- `disabled`
- `runtime_echo`
- `mock`

Runtime audit only writes records when `PLATFORM_ENABLE_RUNTIME_AUDIT=true` and the mode is `runtime_echo` or `mock`.

## Verified MiddlewareBase API

Verified local AgentScope 2.0.3 imports:

```python
from agentscope.middleware import MiddlewareBase
```

Verified signatures:

```text
MiddlewareBase() -> None
MiddlewareBase.on_acting(self, agent: Agent, input_kwargs: dict, next_handler: Callable[..., AsyncGenerator]) -> AsyncGenerator
```

`on_acting` can wrap raw `toolkit.call_tool` execution. AgentScope source notes that permission checking, input validation, and context writes may occur outside this hook. Therefore this phase does not rely on middleware as the only security boundary.

## Current Coverage

True audit coverage in Phase 2.3.5:

- `runtime_echo_tool` success
- `runtime_echo_tool` denied after permission removal
- `runtime_echo_tool` unexpected error

The audit path is the callable wrapper, not generic `on_acting` capture.

## Audit Record Fields

Runtime audit records are written to the existing JSONL files:

- `PLATFORM_TOOL_AUDIT_LOG_FILE`
- `PLATFORM_TOOL_TRACE_LOG_FILE`

Record shape:

```json
{
  "trace_id": "...",
  "event_type": "runtime_tool_call",
  "source": "agentscope_runtime",
  "tenant_id": "tenantA",
  "user_id": "userA",
  "scoped_user_id": "tenantA:userA",
  "agent_id": "agentSmoke",
  "session_id": "sessionSmoke",
  "tool_name": "runtime_echo_tool",
  "allowed": true,
  "timestamp": "...",
  "status": "success",
  "started_at": "...",
  "finished_at": "...",
  "duration_ms": 12,
  "error_code": null
}
```

Denied records use:

```json
{
  "allowed": false,
  "status": "denied",
  "error_code": "RUNTIME_PERMISSION_DENIED"
}
```

No tool input text is written to audit logs.

## Relationship To Phase 2.1 Platform Invoke Audit

Phase 2.1 audit covers:

```text
POST /api/platform/tools/{tool_name}/invoke
```

Phase 2.3.5 audit covers:

```text
AgentScope runtime tool callable for runtime_echo_tool
```

Both write to the same JSONL files. Runtime records include `event_type` and `source` so they can be distinguished from older platform invoke records. Existing `/api/platform/audit/tool-calls` can read these records because tenant/user/agent/session/tool fields are compatible.

## Relationship To Phase 2.3.4 Permission Boundary

Phase 2.3.5 does not replace permission checks. It wraps the execution path added in Phase 2.3.4:

1. run execution-time permission check
2. return echo text on success
3. write success audit
4. write denied audit if permission is removed
5. re-raise permission errors so behavior remains clear

## Local Smoke Test

### A. Default Closed

```powershell
conda run -n agent-platform python -m compileall backend\app

conda run -n agent-platform python -c "import asyncio; from backend.app.tools.factory import build_extra_agent_tools; print(asyncio.run(build_extra_agent_tools('tenantA:userA','agentSmoke','sessionSmoke')))"
```

Expected:

```text
[]
```

### B. Enabled Runtime Tools + Audit + Allow

Use a temporary permission file and audit file. Expected:

- adapter returns `runtime_echo_tool`
- first call succeeds
- audit JSONL contains `source=agentscope_runtime`
- status is `success`
- `trace_id` and `duration_ms` exist

### C. Delete Allow And Call Same Callable

Expected:

- same constructed callable raises `RuntimeToolPermissionDenied`
- audit JSONL contains `status=denied`
- `allowed=false`
- `error_code=RUNTIME_PERMISSION_DENIED`

### D. Platform Invoke Regression

Existing platform invoke flow is unchanged:

- `POST /api/platform/tools/echo_tool/invoke`
- `POST /api/platform/tools/slow_tool/invoke`
- `GET /api/platform/audit/tool-calls`

### E. Tenant Isolation

Runtime audit records include tenant and user fields. `/api/platform/audit/tool-calls` filters by current `X-Tenant-ID` and `X-User-ID`, so tenantB should not see tenantA runtime records.

## ECS Smoke Test

After commit and push:

```bash
cd /app/agent-platform
git pull
source .venv/bin/activate
python -m compileall backend/app
```

Default `.env` should remain:

```env
PLATFORM_ENABLE_RUNTIME_TOOLS=false
PLATFORM_RUNTIME_TOOLS_MODE=disabled
PLATFORM_ENABLE_RUNTIME_AUDIT=false
PLATFORM_RUNTIME_AUDIT_MODE=disabled
```

Restart backend on port `8891` and verify Phase 1.5 chat/session/message still works.

For isolated Python runtime tests, explicitly set:

```env
PLATFORM_ENABLE_RUNTIME_TOOLS=true
PLATFORM_RUNTIME_TOOLS_MODE=mock
PLATFORM_ENABLE_RUNTIME_AUDIT=true
PLATFORM_RUNTIME_AUDIT_MODE=runtime_echo
PLATFORM_TOOL_PERMISSION_FILE=config/tool-permissions.local.json
PLATFORM_TOOL_AUDIT_LOG_FILE=logs/tool-calls-audit.jsonl
```

Then verify success and denied audit records. This phase does not require the model to automatically call `runtime_echo_tool` in chat.

## Current Limits

- Generic runtime tool auditing through `on_acting` is not complete.
- Runtime audit is currently guaranteed only for `runtime_echo_tool`.
- No MCP or Skills.
- No shell, system command, file delete, network, or real enterprise tools.
- Audit writes are JSONL and not production-grade observability.
- Audit write failures are logged and do not replace business exceptions.

## Next Step: Phase 2.3.6

Recommended next phase:

- broaden runtime audit middleware after more AgentScope tool event shapes are verified
- optionally wire AgentScope `PermissionContext` mapper from Phase 2.3.4
- keep default runtime tools and runtime audit disabled
- keep MCP and Skills disabled until governance is mature

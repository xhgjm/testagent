# Phase 2.3.6: Runtime Workspace Alignment

## Goal

Phase 2.3.6 aligns the experimental AgentScope runtime tool path with the
platform workspace isolation model.

The platform already has:

- Phase 1 AgentScope `create_app` integration
- Phase 1.5 platform facade and `tenant_id:user_id` isolation
- Phase 2 workspace, tool, permission, and audit primitives
- Phase 2.1 permission admin, workspace files/cleanup, timeout, and tracing
- Phase 2.3.4 runtime permission boundary
- Phase 2.3.5 runtime audit/tracing for `runtime_echo_tool`

This phase adds a runtime workspace context before injecting the safe
`runtime_echo_tool`. It does not implement a custom AgentScope
`WorkspaceManager`.

## Default Closed

Runtime tools are still disabled by default:

```env
PLATFORM_ENABLE_RUNTIME_TOOLS=false
PLATFORM_RUNTIME_TOOLS_MODE=disabled
```

Runtime audit is also disabled by default:

```env
PLATFORM_ENABLE_RUNTIME_AUDIT=false
PLATFORM_RUNTIME_AUDIT_MODE=disabled
```

With default settings, `build_extra_agent_tools(...)` returns `[]`, and the
AgentScope chat path remains unchanged.

## New Module

```text
backend/app/platform/runtime_workspace.py
```

It defines:

```python
@dataclass(frozen=True)
class RuntimeWorkspaceContext:
    tenant_id: str
    user_id: str
    scoped_user_id: str
    agent_id: str
    session_id: str
    workspace_path: str
    exists: bool
    created: bool
    isolation_strategy: str = "tenant_id/user_id/agent_id/session_id"
```

The resolver is:

```python
def resolve_runtime_workspace(
    settings,
    scoped_user_id,
    agent_id,
    session_id,
    *,
    create=True,
) -> RuntimeWorkspaceContext | None:
    ...
```

It parses `scoped_user_id` as `tenant_id:user_id` and reuses the existing
platform workspace resolver. It does not accept arbitrary paths.

## Isolation Strategy

Runtime workspace paths use the same strategy as the platform API:

```text
WORKSPACE_BASEDIR / tenant_id / user_id / agent_id / session_id
```

The underlying resolver validates that the final path stays under
`WORKSPACE_BASEDIR`. Path traversal such as `../` is sanitized and cannot escape
the configured base directory.

## Runtime Tool Injection Flow

`runtime_echo_tool` is injected only when all conditions pass:

1. `PLATFORM_ENABLE_RUNTIME_TOOLS=true`
2. `PLATFORM_RUNTIME_TOOLS_MODE` is `mock`, `mock_safe`, or `runtime_echo`
3. `user_id` from AgentScope is a scoped platform user id such as `tenantA:userA`
4. `runtime_echo_tool` is registered and enabled
5. platform permission JSON explicitly allows the tool
6. runtime workspace context resolves successfully

If workspace resolution fails, the adapter logs the error and returns `[]`.
Chat should not fail because of runtime workspace alignment.

## Runtime Echo Safety

`runtime_echo_tool` still only returns:

```json
{
  "text": "..."
}
```

It does not:

- read workspace files
- write workspace files
- list workspace files
- delete files
- access network
- execute shell or system commands
- read environment variables
- expose `workspace_path` to the model/tool output

The workspace context is bound internally for governance and audit only.

## Audit / Tracing Fields

When runtime audit is explicitly enabled, runtime audit records can include:

```json
{
  "workspace_path": "...",
  "workspace_exists": true,
  "workspace_created": true,
  "workspace_isolation_strategy": "tenant_id/user_id/agent_id/session_id"
}
```

Existing fields remain unchanged:

- `trace_id`
- `event_type`
- `source`
- `tenant_id`
- `user_id`
- `scoped_user_id`
- `agent_id`
- `session_id`
- `tool_name`
- `allowed`
- `status`
- `started_at`
- `finished_at`
- `duration_ms`
- `error_code`

Runtime audit still does not record user input text or file contents.

Older JSONL records without workspace fields remain valid and can still be read
by `GET /api/platform/audit/tool-calls`.

## What This Phase Does Not Do

- It does not replace AgentScope `LocalWorkspaceManager`.
- It does not implement a custom AgentScope `WorkspaceManager`.
- It does not add a new external API.
- It does not enable MCP or Skills.
- It does not add dangerous tools.
- It does not give runtime tools file read/write capability.
- It does not implement RAG, Long-term Memory, Agent Team, or frontend.

## Local Smoke Test

### 1. Syntax Check

```powershell
conda run -n agent-platform python -m compileall backend\app
```

### 2. Default Closed

```powershell
conda run -n agent-platform python -c "import asyncio; from backend.app.tools.factory import build_extra_agent_tools; print(asyncio.run(build_extra_agent_tools('tenantA:userA','agentSmoke','sessionSmoke')))"
```

Expected:

```text
[]
```

### 3. Resolve Runtime Workspace

```powershell
conda run -n agent-platform python -c "from backend.app.config import Settings; from backend.app.platform.runtime_workspace import resolve_runtime_workspace; s=Settings(workspace_basedir='tmp/runtime-workspaces-smoke'); ctx=resolve_runtime_workspace(s,'tenantA:userA','agentSmoke','sessionSmoke'); print(ctx)"
```

Expected:

- `tenant_id='tenantA'`
- `user_id='userA'`
- `agent_id='agentSmoke'`
- `session_id='sessionSmoke'`
- `isolation_strategy='tenant_id/user_id/agent_id/session_id'`
- `workspace_path` is under `tmp/runtime-workspaces-smoke`

### 4. Compare With Platform Workspace Resolver

For the same tenant, user, agent, and session, `resolve_runtime_workspace(...)`
should return the same path as `ensure_workspace_path(...)`.

### 5. Enabled Runtime Tool With Allow

Use a temporary permission file that allows `runtime_echo_tool`:

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

Set:

```env
PLATFORM_ENABLE_RUNTIME_TOOLS=true
PLATFORM_RUNTIME_TOOLS_MODE=mock
PLATFORM_ENABLE_RUNTIME_AUDIT=true
PLATFORM_RUNTIME_AUDIT_MODE=runtime_echo
```

Expected:

- adapter returns `runtime_echo_tool`
- call succeeds
- audit JSONL has `workspace_path`
- audit JSONL has `workspace_isolation_strategy`
- audit JSONL does not include the input text

### 6. Delete Allow And Call Same Callable

Expected:

- callable raises `RuntimeToolPermissionDenied`
- denied audit record is written
- denied audit record includes workspace fields

### 7. Tenant Isolation

Expected:

- tenantA runtime workspace path is under `tenantA/userA/...`
- tenantB runtime workspace path is under `tenantB/userA/...`
- tenantB cannot see tenantA audit records through
  `GET /api/platform/audit/tool-calls`

## ECS Smoke Test

After local commit and push:

```bash
cd /app/agent-platform
git pull
source .venv/bin/activate
python -m compileall backend/app
```

Keep defaults closed unless running an isolated experiment:

```env
PLATFORM_ENABLE_RUNTIME_TOOLS=false
PLATFORM_RUNTIME_TOOLS_MODE=disabled
PLATFORM_ENABLE_RUNTIME_AUDIT=false
PLATFORM_RUNTIME_AUDIT_MODE=disabled
```

Restart backend on port `8891` and verify:

- `/platform/health`
- `/api/platform/tools`
- Phase 1.5 chat/session/message smoke tests
- Phase 2 workspace/tool/permission smoke tests

For the runtime experiment, use temporary permission, audit, and trace files.
Do not write real API keys into shell history or files.

## Compatibility

This phase keeps existing APIs unchanged:

- `GET /api/platform/tools`
- `POST /api/platform/tools/{tool_name}/invoke`
- `GET /api/platform/tool-permissions`
- `POST /api/platform/tool-permissions`
- `DELETE /api/platform/tool-permissions/{rule_id}`
- `GET /api/platform/workspaces/resolve`
- `GET /api/platform/workspaces/files`
- `POST /api/platform/workspaces/cleanup-preview`
- `POST /api/platform/workspaces/cleanup`
- Phase 1.5 chat/session/message APIs
- AgentScope native APIs

## Current Limits

- Runtime workspace alignment is only guaranteed for `runtime_echo_tool`.
- Runtime tools are still experimental and default closed.
- Workspace context is bound to runtime tools, but AgentScope's native
  workspace lifecycle is still managed by `LocalWorkspaceManager`.
- Audit writes are JSONL and not a production observability backend.
- JSON permission file concurrent writes still need hardening.

## Next Step: Phase 2.3.7

Recommended next phase:

- run runtime tool full regression for Phase 2.3.3 through Phase 2.3.6
- design AgentScope WorkspaceManager alignment options
- decide whether AgentScope runtime workspace should later be delegated to the
  platform resolver
- do not directly implement a custom WorkspaceManager in Phase 2.3.7
- keep runtime tools disabled by default
- keep MCP and Skills disabled until permission, audit, and workspace
  governance are mature


## ECS Smoke Test Result

Date: 2026-07-01
Port: 8891
Result: Passed

Verified:
- Runtime workspace path follows tenant_id/user_id/agent_id/session_id.
- Runtime workspace path is under /data/agent-platform/workspaces.
- Runtime workspace path is scoped as tenantA/userA/<agent_id>/<session_id>.
- Runtime workspace context includes tenant_id, user_id, scoped_user_id, agent_id, session_id, workspace_path, exists, created, and isolation_strategy.
- runtime_echo_tool still does not read or write workspace files.
- runtime_echo_tool does not expose workspace_path to model/tool output.
- Success runtime audit includes workspace_path, workspace_exists, workspace_created, and workspace_isolation_strategy.
- Denied runtime audit also includes workspace fields.
- Runtime audit does not include sensitive input text.
- Old audit records remain readable even when they do not contain workspace fields.
- No MCP, Skill, shell, file deletion, network access, or enterprise system integration is enabled.

Evidence:
- WORKSPACE_PATH /data/agent-platform/workspaces/tenantA/userA/bf62b14f56b947b8915dd37a7f12aadb/phase236-workspace-smoke-1782901944
- WORKSPACE_EXISTS True
- WORKSPACE_CREATED True
- WORKSPACE_STRATEGY tenant_id/user_id/agent_id/session_id
- FIRST_CALL_OK {'text': 'first call should pass'}
- SECOND_CALL_DENIED
- ERROR_CODE RUNTIME_PERMISSION_DENIED
- success audit includes workspace_path and has_sensitive_text=False
- denied audit includes workspace_path and has_sensitive_text=False

Conclusion:
Phase 2.3.6 runtime workspace alignment passed ECS smoke test.
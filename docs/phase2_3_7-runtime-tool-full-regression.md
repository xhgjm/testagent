# Phase 2.3.7: Runtime Tool Full Regression

## Goal

Phase 2.3.7 closes the Phase 2.3 runtime tool loop with a repeatable local
regression path. It does not add new runtime features.

This phase verifies the stability of:

- `extra_agent_tools` adapter skeleton
- injection-time permission filtering
- execution-time permission re-check
- runtime audit/tracing
- runtime workspace context
- tenant isolation for runtime audit/workspace data

Runtime tools and runtime audit remain disabled by default. MCP, Skills, real
enterprise tools, shell commands, system commands, file deletion, network
access, RAG, Long-term Memory, Agent Team, and frontend are still out of scope.

## Phase 2.3.3 To 2.3.6 Chain Review

Phase 2.3.3 added the default-closed `extra_agent_tools` adapter skeleton. It
proved AgentScope can call a platform async factory with:

```python
async def build_extra_agent_tools(
    user_id: str,
    agent_id: str,
    session_id: str,
) -> list[ToolBase]:
    ...
```

Phase 2.3.4 added runtime permission re-check. The adapter filters tools before
injection, and the bound runtime callable checks permission again before it
returns.

Phase 2.3.5 added runtime audit/tracing for the safe `runtime_echo_tool`.
Success, denied, and error paths can write structured JSONL records with
`trace_id`, `status`, `duration_ms`, and `error_code`.

Phase 2.3.6 added runtime workspace context. The adapter resolves the same
platform isolation path used by `/api/platform/workspaces/resolve`:

```text
WORKSPACE_BASEDIR / tenant_id / user_id / agent_id / session_id
```

## Full Runtime Tool Flow

```text
create_app(extra_agent_tools=...)
    -> backend.app.tools.factory.build_extra_agent_tools
    -> backend.app.platform.runtime_tools._build_extra_agent_tools
    -> runtime permission allow check
    -> runtime workspace resolve
    -> build runtime_echo_tool
    -> runtime echo callable execution
    -> execution-time permission re-check
    -> runtime audit/tracing
    -> audit JSONL
    -> /api/platform/audit/tool-calls
```

## Default Closed Strategy

Default `.env.example` remains:

```env
PLATFORM_ENABLE_RUNTIME_TOOLS=false
PLATFORM_RUNTIME_TOOLS_MODE=disabled
PLATFORM_ENABLE_RUNTIME_AUDIT=false
PLATFORM_RUNTIME_AUDIT_MODE=disabled
```

With default settings, the adapter returns `[]`. This preserves the existing
AgentScope chat/session/message path unless runtime tools are explicitly
enabled for an experiment.

## Why runtime_echo_tool Is Still A Safe Mock

`runtime_echo_tool` exists only to prove the runtime extension path. It returns
the input text and does not:

- execute shell or system commands
- read, write, list, or delete files
- access network resources
- read environment variables
- call real enterprise systems
- connect MCP or Skills

This keeps the regression test focused on governance mechanics rather than tool
capability.

## Why MCP, Skills, And Real Tools Stay Disabled

MCP, Skills, and enterprise tools need stronger governance before runtime
enablement:

- tenant/user/agent permission policy
- parameter schema validation
- timeout and cancellation behavior
- audit/tracing coverage
- workspace and secret boundaries
- lifecycle and cleanup behavior

Phase 2.3.7 is a regression and design phase, not a capability expansion phase.

## Why Audit Does Not Record User Input Text

Runtime audit records management metadata:

- who called
- which tenant/user/agent/session
- which tool
- whether it was allowed
- status and error code
- timing
- workspace context

It intentionally does not store user input text or file contents. That avoids
turning audit logs into a second sensitive data store.

## Why workspace_path Is Management-Side Only

`workspace_path` is useful for audit traceability and operational debugging. It
is not returned by `runtime_echo_tool` and should not be shown to the model as a
tool result.

The path is an internal platform/runtime boundary. Future filesystem-capable
tools must receive only the minimum workspace capability they need, and only
after permission, audit, and cleanup rules are mature.

## Platform Invoke API vs Runtime Tool Calling

Platform invoke API:

```text
POST /api/platform/tools/{tool_name}/invoke
```

This is a platform-owned active invocation path for admin tests and management
debugging.

Runtime tool calling:

```text
extra_agent_tools -> AgentScope runtime toolkit -> model/tool execution
```

This is the path AgentScope uses during chat. It does not replace platform
invoke. Both paths remain compatible.

## Tenant Isolation

Phase 1.5 forwards platform users to AgentScope with:

```text
scoped_user_id = tenant_id:user_id
```

The runtime adapter parses that scoped id. Tenant isolation is enforced by:

- permission rules keyed by `tenant_id`, `user_id`, `agent_id`, and `tool_name`
- runtime workspace paths keyed by `tenant_id/user_id/agent_id/session_id`
- audit filtering in `/api/platform/audit/tool-calls`

`tenantA:userA` and `tenantB:userA` resolve to different workspace paths and
different audit query scopes.

## Local Smoke Script

New script:

```text
scripts/smoke_phase2_3_7_runtime_tools.py
```

It does not rely on real `.env`, does not start the backend server, does not
access network, and does not touch production permission/audit/workspace files.
It creates temporary files with `tempfile.TemporaryDirectory()`.

Run:

```powershell
python scripts/smoke_phase2_3_7_runtime_tools.py
```

Recommended local environment:

```powershell
conda run -n agent-platform python scripts/smoke_phase2_3_7_runtime_tools.py
```

Coverage:

- default disabled adapter returns `[]`
- explicitly enabled adapter without allow returns `[]`
- enabled plus allow returns `runtime_echo_tool`
- first callable execution succeeds while allow exists
- same callable is denied after allow removal
- success and denied audit records are written
- `trace_id`, `duration_ms`, `error_code`, and workspace fields are present
- audit records do not include input text
- tenantB workspace path differs from tenantA
- tenantB cannot read tenantA audit records through the platform audit reader

## Compile Checks

```powershell
python -m compileall backend/app
python -m compileall scripts
```

Use the project Python 3.11 environment on Windows:

```powershell
conda run -n agent-platform python -m compileall backend/app
conda run -n agent-platform python -m compileall scripts
```

## Current Limits

- Runtime tool coverage is still limited to `runtime_echo_tool`.
- Generic runtime audit middleware is not complete.
- AgentScope `PermissionContext` is not wired to platform permission rules.
- Runtime workspace context is bound to the tool wrapper, but AgentScope's
  native `LocalWorkspaceManager` still owns the runtime workspace lifecycle.
- JSON permission and audit files are not production-grade concurrent storage.
- MCP and Skills remain disabled.

## Phase 2.4 Recommendation

Phase 2.4 should close Phase 2 platform foundations:

- normalize smoke scripts and docs
- review API compatibility
- clean up phase overview status
- add focused tests around permission/audit/workspace helpers
- keep runtime tools default closed
- avoid MCP/Skill enablement until governance is mature

## Phase 3 Recommendation

Phase 3 should start RAG through the platform facade plus AgentScope RAG
Service. Do not begin Phase 3 by replacing AgentScope `WorkspaceManager`.

Recommended Phase 3 starting point:

- KnowledgeBase facade
- Document upload metadata flow
- BlobStore and vector-store configuration
- async index worker smoke test
- tenant/user knowledge isolation

# Phase 2.4: Runtime Tool Governance Closure

## A. Goal

Phase 2.4 closes the Phase 2 runtime tool governance work. It is not a new
RAG, MCP, Skill, Long-term Memory, Agent Team, frontend, or production tool
integration phase.

The goal is to summarize what Phase 2 completed, keep API compatibility clear,
standardize smoke testing, and define the boundary for Phase 3 RAG Service.

No official AgentScope source code is changed. No real `.env` file is touched.
No ECS file is modified directly. Runtime tools and runtime audit remain
disabled by default.

## B. Phase 2 Capability Overview

| Phase | Goal | Status | ECS passed | Runtime main chain changed | Default closed | Key files |
| --- | --- | --- | --- | --- | --- | --- |
| Phase 2 | Workspace + Tool + Permission + Audit | Completed | Yes | No | N/A | `backend/app/platform/workspace.py`, `tools.py`, `permissions.py`, `audit.py`, `routes.py`, `docs/phase2-workspace-tool-permission.md` |
| Phase 2.1 | Permission Admin + Workspace Files/Cleanup + Tool Timeout + Structured Tracing | Completed | Yes | No | N/A | `backend/app/platform/routes.py`, `schemas.py`, `docs/phase2_1-hardening.md` |
| Phase 2.2 | AgentScope Native Alignment Design | Completed | Design only | No | N/A | `docs/phase2_2-agentscope-native-alignment.md` |
| Phase 2.3.1 | Tool native metadata | Completed | Yes | No | N/A | `backend/app/platform/tools.py`, `schemas.py`, `docs/phase2_3_1-tool-metadata.md` |
| Phase 2.3.2 | `extra_agent_tools` adapter signature verification | Completed | Design only | No | N/A | `docs/phase2_3_2-extra-agent-tools-adapter-design.md` |
| Phase 2.3.3 | `extra_agent_tools` adapter skeleton | Completed | Yes | Yes, but default returns `[]` | Yes | `backend/app/platform/runtime_tools.py`, `backend/app/tools/factory.py`, `docs/phase2_3_3-extra-agent-tools-skeleton.md` |
| Phase 2.3.4 | Runtime permission boundary | Completed | Yes | Yes, only for explicit runtime mock path | Yes | `backend/app/platform/runtime_permissions.py`, `runtime_tools.py`, `docs/phase2_3_4-runtime-permission-boundary.md` |
| Phase 2.3.5 | Runtime audit/tracing | Completed | Yes | Yes, only for explicit runtime mock path | Yes | `backend/app/platform/runtime_audit.py`, `runtime_middlewares.py`, `docs/phase2_3_5-runtime-audit-middleware.md` |
| Phase 2.3.6 | Runtime workspace alignment | Completed | Yes | Yes, only for explicit runtime mock path | Yes | `backend/app/platform/runtime_workspace.py`, `runtime_tools.py`, `runtime_audit.py`, `docs/phase2_3_6-runtime-workspace-alignment.md` |
| Phase 2.3.7 | Runtime full regression + WorkspaceManager alignment design | Completed | Yes | No | Yes | `scripts/smoke_phase2_3_7_runtime_tools.py`, `docs/phase2_3_7-runtime-tool-full-regression.md`, `docs/phase2_3_7-workspace-manager-alignment-design.md` |
| Phase 2.4 | Closure | Completed locally | Pending ECS after Git sync | No | Yes | `docs/phase2_4-runtime-tool-governance-closure.md`, `scripts/smoke_phase2_4_runtime_governance.py` |

## C. Current Runtime Tool Governance Architecture

```text
Platform API / AgentScope create_app
    -> extra_agent_tools adapter
    -> runtime tools default closed
    -> explicit mock mode
    -> permission allow filter before injection
    -> runtime workspace resolve
    -> FunctionTool(runtime_echo_tool)
    -> execution-time permission re-check
    -> runtime audit/tracing
    -> audit JSONL
    -> /api/platform/audit/tool-calls
```

The runtime path is intentionally conservative. The only runtime tool currently
used for regression is `runtime_echo_tool`, a safe mock that does not access
files, network, shell commands, environment variables, MCP, Skills, or real
enterprise systems.

## D. Platform Invoke API vs Runtime Tool Calling

Platform invoke API:

```text
POST /api/platform/tools/{tool_name}/invoke
```

This is a platform-owned active invocation path. It remains available for
management-side testing, debugging, and future platform-initiated tool calls.

Runtime tool calling:

```text
AgentScope chat -> extra_agent_tools -> Agent runtime toolkit
```

This is the foundation for future Agent automatic tool usage during chat.

Both paths are governed by platform policy, but they are different execution
paths. Phase 2.4 keeps both paths compatible and does not replace platform
invoke with runtime tool calling.

## E. Permission Closure

Current permission model:

- default deny
- platform permission JSON is the current policy source
- Tool Permission Admin API can create, list, and delete allow rules
- platform invoke uses Phase 2.1 permission checks
- runtime tool injection uses an allow filter before injection
- runtime tool execution performs a second permission re-check
- deleting an allow rule makes an already constructed runtime callable fail with
  `RUNTIME_PERMISSION_DENIED`

Current limitations:

- AgentScope `PermissionContext` is not deeply integrated yet.
- `PermissionRule` mapper helpers exist as design/building blocks, not a
  complete production permission system.
- JSON permission files are not production-grade concurrent policy storage.

## F. Audit / Tracing Closure

Platform invoke audit records include:

- `trace_id`
- `tenant_id`
- `user_id`
- `agent_id`
- `session_id`
- `tool_name`
- `allowed`
- `status`
- `started_at`
- `finished_at`
- `duration_ms`
- `error_code`

Runtime tool audit records include:

- `trace_id`
- `event_type=runtime_tool_call`
- `source=agentscope_runtime`
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

Success and denied runtime calls both write audit when runtime audit is
explicitly enabled. Audit records do not store full user input text or file
contents.

`GET /api/platform/audit/tool-calls` can read older platform records and newer
runtime records because the tenant/user/agent/session/tool fields remain
compatible. Tenant isolation is enforced by the existing audit reader filters.

## G. Workspace Closure

Platform workspace path policy:

```text
WORKSPACE_BASEDIR / tenant_id / user_id / agent_id / session_id
```

Runtime workspace context reuses the platform resolver and adds these fields to
runtime audit:

- `workspace_path`
- `workspace_exists`
- `workspace_created`
- `workspace_isolation_strategy`

`runtime_echo_tool` does not read or write workspace files. It also does not
return `workspace_path` to model/tool output. The path is management-side audit
metadata only.

Custom AgentScope `WorkspaceManager` is not implemented in Phase 2. AgentScope
2.0.3 `LocalWorkspaceManager` was verified to use `basedir/agent_id` for local
workdirs, while the platform resolver uses
`basedir/tenant_id/user_id/agent_id/session_id`. A future
`PlatformWorkspaceManager` needs careful design and smoke testing before it is
wired into `create_app`.

## H. Tool Registry Closure

Current tool metadata:

- `tool_name`
- `name`
- `description`
- `native_type`
- `native_ref`
- `timeout_seconds`
- `enabled`
- `input_schema`
- `default_timeout_seconds`

Current tools:

- `echo_tool`: platform mock invoke
- `time_tool`: platform mock invoke
- `slow_tool`: platform timeout smoke
- `runtime_echo_tool`: runtime safe mock

Current `native_type` values are primarily `mock`. The schema is ready for
future `agentscope_tool`, `mcp`, and `skill` metadata, but Phase 2 does not
connect MCP, Skills, or real enterprise tools.

## I. Default Closed Strategy

Default runtime settings:

```env
PLATFORM_ENABLE_RUNTIME_TOOLS=false
PLATFORM_RUNTIME_TOOLS_MODE=disabled
PLATFORM_ENABLE_RUNTIME_AUDIT=false
PLATFORM_RUNTIME_AUDIT_MODE=disabled
```

Default behavior:

- runtime tools are not injected
- runtime audit does not write records
- chat/session/message behavior is not affected by runtime tool experiments
- only explicit enablement plus permission allow can inject `runtime_echo_tool`

## J. API Compatibility

Phase 2.4 does not delete, rename, or change request bodies for these APIs:

- `GET /api/platform/overview`
- `POST /api/platform/credentials`
- `POST /api/platform/agents`
- `GET /api/platform/agents`
- `POST /api/platform/sessions`
- `GET /api/platform/sessions`
- `POST /api/platform/chat`
- `GET /api/platform/sessions/{session_id}/messages`
- `GET /api/platform/sessions/{session_id}/stream-url`
- `GET /api/platform/workspaces/resolve`
- `GET /api/platform/workspaces/files`
- `POST /api/platform/workspaces/cleanup-preview`
- `POST /api/platform/workspaces/cleanup`
- `GET /api/platform/tools`
- `POST /api/platform/tools/{tool_name}/invoke`
- `GET /api/platform/tool-permissions`
- `POST /api/platform/tool-permissions`
- `DELETE /api/platform/tool-permissions/{rule_id}`
- `GET /api/platform/audit/tool-calls`

AgentScope native APIs also remain available for low-level debugging.

## K. Smoke Test Status

Historical ECS smoke status:

- Phase 1.5 ECS smoke passed
- Phase 2 ECS smoke passed
- Phase 2.1 ECS smoke passed
- Phase 2.3.1 ECS smoke passed
- Phase 2.3.3 ECS smoke passed
- Phase 2.3.4 ECS smoke passed
- Phase 2.3.5 ECS smoke passed
- Phase 2.3.6 ECS smoke passed
- Phase 2.3.7 ECS smoke passed

Current runtime governance smoke source of truth:

```bash
python scripts/smoke_phase2_3_7_runtime_tools.py
```

Phase 2.4 also provides a thin wrapper:

```bash
python scripts/smoke_phase2_4_runtime_governance.py
```

The wrapper calls the Phase 2.3.7 smoke script and prints:

```text
Phase 2.4 runtime governance smoke passed.
```

## L. Current Limits

- Runtime tool coverage currently includes only safe mock `runtime_echo_tool`.
- MCP is not connected.
- Skill is not connected.
- RAG is not connected.
- Long-term Memory is not connected.
- Agent Team is not connected.
- Frontend is not implemented.
- Custom WorkspaceManager is not implemented.
- AgentScope `PermissionContext` is not deeply integrated.
- JSON permission and audit files are not production-grade concurrent storage.
- This is a platform governance skeleton and regression basis, not a complete
  enterprise production governance system.

## M. Phase 3 RAG Boundary Recommendation

Phase 3 should start RAG Service work without rewriting AgentScope RAG.

Recommendations:

- use AgentScope RAG Service and building blocks first
- add a platform RAG facade for:
  - knowledge base management
  - tenant/user isolation
  - document metadata
  - permission
  - audit
  - Agent-KB binding
- do not start Phase 3 by changing custom WorkspaceManager
- do not connect MCP or Skills at the beginning of Phase 3
- design the RAG Service architecture first, then implement a minimal facade

This keeps Phase 3 aligned with the platform principle: AgentScope provides the
runtime building blocks, while the platform layer owns enterprise isolation,
API facade, permission, audit, and operational governance.

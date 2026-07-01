# Phase 2.2: AgentScope Native Tool / Permission / Workspace Alignment

## 1. Background

Phase 2.2 is a design and gap-analysis phase. It does not rewrite the existing platform implementation, does not modify ECS, does not modify official AgentScope source code, and does not change runtime behavior.

The platform has already completed these foundations:

- Phase 1: AgentScope `create_app` is the backend entrypoint, with Credential, Agent, Session, Chat, SSE, and Message History available through native AgentScope Agent Service APIs.
- Phase 1.5: `/api/platform/*` API facade is the recommended enterprise entrypoint. It uses `X-Tenant-ID` and `X-User-ID`, then forwards to AgentScope with `scoped_user_id = tenant_id:user_id`.
- Phase 2: Workspace resolve, mock tool registry, default-deny permission checks, explicit allow rules, and tool audit logs are available at the platform layer.
- Phase 2.1: Tool Permission Admin API, workspace files, cleanup preview/cleanup, tool timeout, `slow_tool`, structured tracing, `trace_id`, `duration_ms`, and `error_code` are available.

The purpose of this phase is to align the platform-layer Tool, Permission, Workspace, Audit, and Tracing model with AgentScope 2.0.3 native building blocks. Phase 2.3.1 starts this work by adding native alignment metadata to the platform tool registry. Later implementation phases should make Agent runtime tool calling go through AgentScope Toolkit, Permission System, Workspace, and Middleware rather than treating platform tool invocation as the runtime path.

References:

- AgentScope Agent Service: https://docs.agentscope.io/versions/2.0.3/zh/deploy/agent-service
- AgentScope Tool: https://docs.agentscope.io/versions/2.0.3/zh/building-blocks/tool
- AgentScope Permission System: https://docs.agentscope.io/versions/2.0.3/en/building-blocks/permission-system
- AgentScope Workspace: https://docs.agentscope.io/versions/2.0.3/en/building-blocks/workspace

## 2. Current Platform Implementation

The current platform implementation is intentionally conservative and sits above AgentScope Agent Service:

- Platform API facade: `/api/platform/*` wraps native AgentScope APIs and hides low-level request shapes from enterprise callers.
- Scoped identity: `scoped_user_id = tenant_id:user_id` maps multi-tenant identity into AgentScope's native `user_id` ownership boundary.
- Workspace resolve/files/cleanup: platform workspace paths use `tenant_id/user_id/agent_id/session_id`; file listing and cleanup stay under the resolved workspace root.
- Platform tools: `echo_tool`, `time_tool`, and `slow_tool` are safe mock tools for platform validation. They do not execute shell commands or touch real enterprise systems.
- Permission storage: tool permission rules are loaded from the JSON file configured by `PLATFORM_TOOL_PERMISSION_FILE`.
- Tool Permission Admin API: platform users can list, add, and delete only their own tenant/user scoped rules.
- Permission behavior: default deny remains the baseline; explicit allow is required before invoking a platform tool.
- Audit JSONL: tool invocation attempts are written to the configured audit log file.
- Structured tracing: each tool invocation produces `trace_id`, `status`, `duration_ms`, `error_code`, `started_at`, and `finished_at`.

Important boundary: current Phase 2.1 permission and tracing protect `/api/platform/tools/{tool_name}/invoke`. They do not yet govern AgentScope runtime tool calls produced during `/chat`.

## 3. AgentScope Native Capability Summary

AgentScope Agent Service is a FastAPI-based service for multi-tenant and multi-session agents. It manages resources such as credentials, agents, sessions, messages, schedules, workspace lifecycle, and event streaming. AgentScope documentation states that resources are owned under request `user_id`; our platform uses `tenant_id:user_id` as that value to obtain basic tenant isolation.

`create_app` is the integration point used by this project. It receives storage, message bus, and workspace manager instances. It also supports custom extension points such as `extra_agent_tools` and `extra_agent_middlewares`.

`extra_agent_tools` is an async factory with the shape `(user_id, agent_id, session_id) -> Awaitable[list[ToolBase]]`. AgentScope calls it when assembling an agent for a chat or schedule run. The returned tools are merged with workspace-derived tools into the toolkit's basic group. This is the correct future entrypoint for tenant/user/agent/session aware enterprise tools.

`extra_agent_middlewares` is an async factory with the shape `(user_id, agent_id, session_id) -> Awaitable[list[MiddlewareBase]]`. AgentScope calls it when assembling an agent. Returned middleware can add runtime audit, tracing, tenant checks, budget controls, or policy hooks around the agent run.

AgentScope Toolkit is the native container for tools, MCP clients, skills, and tool groups. A Tool is any object implementing `ToolBase`, including built-in tools, `FunctionTool` wrappers, and `MCPTool` adapters. MCP clients let AgentScope discover and adapt external MCP-compatible tools. Skills are markdown-based instruction packs: they are not directly called like tools; an agent reads a skill through a viewer and then uses available tools to execute the instructions.

AgentScope Permission System intercepts tool calls and decides allow, deny, or ask. It combines explicit rules, a permission mode, and tool-level runtime safety checks. The documented modes include `DEFAULT`, `EXPLORE`, `ACCEPT_EDITS`, `BYPASS`, and `DONT_ASK`. A native `PermissionRule` includes `tool_name`, `rule_content`, `behavior`, and `source`. Exact import paths and any private/internal class names should still be verified against the installed AgentScope 2.0.3 source before implementation.

AgentScope Workspace is the execution environment for tools, MCPs, skills, and context offloading. AgentScope provides local filesystem, Docker, and E2B workspace implementations, plus WorkspaceManager classes used by Agent Service. Workspace managers allocate, cache, and close workspaces and determine the isolation policy. Official docs describe built-in managers as generally isolating by agent or by user/agent depending on backend; a custom manager can be used for per-user, per-session, or hybrid isolation.

AgentScope workspace also participates in MCP and Skill lifecycle. The workspace can persist MCP configs, skill directories, offloaded context, and oversized tool results. For Docker and E2B workspaces, an MCP gateway bridges host-side calls to MCP servers inside the isolated environment.

## 4. Gap Analysis

| Capability | Current Platform Implementation | AgentScope Native Capability | Gap | Recommended Next Step |
| --- | --- | --- | --- | --- |
| Tool Registry | In-memory registry for `echo_tool`, `time_tool`, `slow_tool` | Toolkit registers `ToolBase`, `FunctionTool`, MCP tools, skills, and groups | Platform registry is not mapped to native toolkit | Add `native_type` and `native_ref` metadata in Phase 2.3 |
| Tool Invocation | `/api/platform/tools/{tool_name}/invoke` actively invokes mock tools | Agent runtime invokes tools inside ReAct/tool-calling through Toolkit | Platform invoke is not chat runtime tool calling | Keep platform invoke for admin/testing; add `extra_agent_tools` adapter for runtime |
| Tool Permission | JSON allow-list checks platform invoke only | Permission System checks every Agent runtime tool call | Runtime `/chat` tool calls are not governed by platform rules yet | Map platform rules to native permission context/rules |
| Permission Admin | `/api/platform/tool-permissions` manages tenant/user scoped JSON rules | Native PermissionRule supports allow/deny/ask behavior and tool-specific matching | Platform rules are simpler and allow-only | Extend schema later with `effect`, `rule_content`, and `source`; keep default deny |
| Audit / Tracing | JSONL audit and trace for platform invoke | Middleware can intercept agent lifecycle and tool-call related behavior | Runtime tool calls do not emit platform trace records yet | Implement runtime audit middleware through `extra_agent_middlewares` |
| Workspace Resolve | Platform path is `tenant_id/user_id/agent_id/session_id` | WorkspaceManager decides workspace identity and lifecycle | Native LocalWorkspaceManager does not currently use the exact platform path policy | Design custom WorkspaceManager for tenant/user/agent/session isolation |
| Workspace Files / Cleanup | Platform lists and cleans files under resolved workspace path | Workspace owns files, MCP configs, skills, context offload, and tool-result offload | Platform file APIs are not yet aware of native workspace internal lifecycle | Keep platform APIs; align paths before exposing deeper native workspace artifacts |
| MCP | Not implemented; only reserved | Toolkit can register MCP clients; workspace can persist MCP configs | No platform registry, permissions, timeout, or audit for MCP | Add MCP as `native_type=mcp` after rule schema is expanded |
| Skills | Not implemented; only reserved | Toolkit can register skill loaders; skills are instruction packs, not direct tools | No platform skill catalog or governance | Add skill catalog later with read-only metadata and workspace-scoped installation |
| Agent runtime tool calling | Not implemented beyond native AgentScope defaults | AgentScope assembles toolkit and performs tool calls during chat | Platform mock tool path is separate from runtime path | Introduce runtime tool injection through `extra_agent_tools` |
| create_app extra_agent_tools | Correct async factory currently returns empty list | Native extension point for dynamic tenant/user/session tools | No real ToolBase adapters returned yet | Implement adapter that converts approved platform registry entries to native tools |
| create_app extra_agent_middlewares | Correct async factory currently returns empty list | Native extension point for runtime governance | No audit/tracing/policy middleware returned yet | Implement tenant-aware runtime middleware |
| WorkspaceManager | Current `LocalWorkspaceManager` is passed to `create_app`; platform has separate path resolver | Native manager allocates, caches, evicts, and closes workspaces | Platform resolver and native manager can diverge | Add custom manager or configure manager pathing to use platform isolation policy |

## 5. Recommended Architecture

```text
External Client / HiMarket / Gateway
    |
    v
Platform API /api/platform/*
    |
    v
tenant/user identity, permission, audit, tracing
    |
    v
AgentScope Agent Service create_app
    |
    v
Agent Runtime / Toolkit / Permission / Workspace / MCP / Skills
```

The platform API remains the enterprise entrypoint. External callers should prefer `/api/platform/*`; native AgentScope APIs remain available for low-level debugging and smoke testing.

AgentScope remains the Agent runtime. The platform layer should not replace AgentScope Toolkit. It should manage, expose, and govern which tools are available, then inject native tools through AgentScope extension points.

The platform layer should not replace AgentScope Permission System. It should own enterprise policy and map those policies into native permission constructs for runtime execution.

The platform layer should not replace AgentScope Workspace. It should define the enterprise isolation policy and align AgentScope WorkspaceManager with that policy.

## 6. Tool Alignment Design

The platform tool registry should remain as the enterprise-visible catalog. It is the place where product/admin APIs can show which tools exist, who can use them, and what the governance status is.

Tool metadata now starts to include these native alignment fields:

- `native_type`: one of `mock`, `agentscope_tool`, `mcp`, or `skill`.
- `native_ref`: a pointer to the native tool class, MCP server/tool name, or skill name/path.
- `timeout_seconds`: platform-level default execution timeout exposed to clients.
- `enabled`: whether the tool is enabled in the platform registry.

Future tool metadata may also include:

- `risk_level`: optional future field for review workflows.
- `read_only`: optional future field to map into AgentScope permission modes and read-only behavior.

Current mock tools should remain safe. `echo_tool`, `time_tool`, and `slow_tool` continue to validate permission, timeout, audit, and tracing without connecting to real enterprise systems.

Real tools should be registered through AgentScope Toolkit. For simple Python tools, Phase 2.3 can wrap platform handlers as AgentScope-native tools only after verifying `ToolBase` or `FunctionTool` signatures in the installed AgentScope 2.0.3 source. For MCP tools, the platform registry should store server/tool identity and let AgentScope MCP adapters handle protocol negotiation and tool discovery.

`/api/platform/tools/{tool_name}/invoke` should remain as platform active invocation and smoke-test API. It is useful for admin validation, permission testing, timeout testing, and audit/tracing verification.

Agent runtime automatic tool calling should go through AgentScope Toolkit and `extra_agent_tools`, not through `/api/platform/tools/{tool_name}/invoke`.

Current Phase 2.1 tool invoke is platform active tool invocation. It is not yet Agent automatic tool calling during chat.

## 7. Permission Alignment Design

Platform permission rules remain the enterprise policy source. Default deny remains unchanged.

The platform rule model should evolve toward:

- `tenant_id`
- `user_id`
- `agent_id`
- `tool_name`
- `effect`: `allow`, `deny`, or later `ask`
- `rule_content`: optional native matching pattern
- `source`: `platformAdmin`, `tenantPolicy`, `session`, or similar

Phase 2.1 stores allow rules only. Phase 2.3 should introduce a schema-compatible path that can later map platform rules to AgentScope `PermissionRule` values. AgentScope's native model supports `ALLOW`, `DENY`, and `ASK`; the platform should still keep enterprise backend behavior to allow/deny first and postpone user-facing ASK workflows.

The platform Tool Permission Admin API should continue to manage enterprise rules. It must not allow callers to spoof `tenant_id` or `user_id` through request bodies or query strings.

When Agent runtime tool calling is enabled, permission must apply inside the AgentScope runtime path. That can be done by constructing a native permission context from platform rules, by injecting middleware, or by using AgentScope permission hooks after exact 2.0.3 source verification.

Current Phase 2.1 permission only protects the platform tool invoke API. Future work must apply permission to AgentScope runtime tool calling.

## 8. Workspace Alignment Design

Current platform workspace pathing is:

```text
{WORKSPACE_BASEDIR}/{tenant_id}/{user_id}/{agent_id}/{session_id}
```

This policy is stronger than the default local AgentScope manager described in the docs because it isolates by tenant, user, agent, and session. The platform should preserve this policy.

Future alignment should consider a custom AgentScope WorkspaceManager so the runtime uses the same workspace path that platform APIs resolve. LocalWorkspace is the first target because it matches the current ECS prototype and does not require Docker/E2B operational dependencies.

DockerWorkspace and E2BWorkspace should remain later directions. They require additional security boundaries, image/runtime configuration, MCP gateway behavior, network policy, and lifecycle controls.

Workspace files and cleanup APIs should continue to be provided by the platform layer. Cleanup should keep `dry_run=true` as the safe default. Path traversal must remain forbidden. Callers must not be able to list or clean another tenant/user workspace.

Before exposing native workspace internals, Phase 2.3 should verify how AgentScope writes `.mcp`, `skills/`, `data/`, and `sessions/` under LocalWorkspace in 2.0.3.

## 9. Audit / Tracing Alignment Design

Current audit records platform tool invocation results:

- allowed
- denied
- timeout
- not_found
- error
- success

Future runtime tool calling must also generate a `trace_id` and write the same structured fields:

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

The recommended runtime path is `extra_agent_middlewares`. Middleware can carry tenant/user/session context and record the lifecycle of runtime tool calls. If exact runtime hooks differ in AgentScope 2.0.3, mark the implementation with source verification before coding.

Phase 2.2 does not introduce OpenTelemetry, Jaeger, or a database. JSONL remains the local prototype format. Production-grade search, retention, and compliance logging should be handled in Phase 6.

## 10. Compatibility With Existing Phases

Phase 1 does not need a refactor. AgentScope `create_app` remains the backend foundation.

Phase 1.5 does not need a refactor. `/api/platform/*` remains the enterprise facade, and native AgentScope APIs remain available for low-level debugging.

Phase 2 and Phase 2.1 APIs should not be deleted or renamed:

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

Phase 2.2 changes no ECS behavior. It is documentation and design only.

## 11. Suggested Phase 2.3 Implementation Split

1. Phase 2.3.1: Extend tool metadata with `native_type`, `native_ref`, `timeout_seconds`, and `enabled`.
2. Phase 2.3.2: Design and implement an `extra_agent_tools` adapter that returns AgentScope-native tools for allowed platform registry entries.
3. Phase 2.3.3: Design a platform rule to AgentScope PermissionRule mapper after verifying exact 2.0.3 import paths and model signatures.
4. Phase 2.3.4: Design a custom WorkspaceManager that aligns AgentScope runtime workspaces with `tenant_id/user_id/agent_id/session_id`.
5. Phase 2.3.5: Design runtime audit middleware through `extra_agent_middlewares`.
6. Phase 2.3.6: Run local smoke tests without real enterprise tools.
7. Phase 2.3.7: Sync through GitHub and run ECS smoke tests on port `8891`.

## 12. Risks And Limits

- AgentScope 2.0.3 documentation and installed source can differ. Exact import paths and class signatures must be verified on ECS or in the local environment before code changes.
- Platform permission JSON file writes are not concurrency-safe enough for production.
- JSONL audit/tracing is suitable for prototype verification, not production search or compliance retention.
- Runtime tool calling and platform invoke API are separate paths. Treating them as the same would create a governance gap.
- A custom WorkspaceManager may affect AgentScope native workspace lifecycle, TTL, MCP process shutdown, and session reuse behavior.
- MCP and Skills require parameter schema, permission, timeout, audit, lifecycle, and security boundaries before enabling tenant-facing usage.
- ASK-mode permission workflows require UX and event handling design. The platform should not enable ASK until it has a clear approval surface.

## 13. Acceptance Criteria

- `docs/phase2_2-agentscope-native-alignment.md` exists.
- The document explains the relationship between current platform capabilities and AgentScope native Tool, Permission, Workspace, MCP, Skill, Middleware, and WorkspaceManager capabilities.
- The document states that Phase 1 and Phase 1.5 do not need refactoring.
- The document states that Phase 2 and Phase 2.1 APIs remain compatible.
- The document clearly separates platform active tool invocation from Agent runtime automatic tool calling.
- The document gives a Phase 2.3 implementation route without implementing code in Phase 2.2.
- No ECS files are changed.
- No official AgentScope source code is changed.
- No real `.env` file is touched.
- Existing Python code still passes `python -m compileall backend/app`.

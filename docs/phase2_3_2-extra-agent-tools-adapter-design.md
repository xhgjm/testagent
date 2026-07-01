# Phase 2.3.2: extra_agent_tools Adapter Design And Signature Verification

## 1. Background

The platform has completed these phases:

- Phase 1: AgentScope `create_app` is the backend entrypoint. Credential, Agent, Session, Chat, SSE, and Message History are available through AgentScope Agent Service.
- Phase 1.5: `/api/platform/*` facade uses `X-Tenant-ID` and `X-User-ID`, then forwards to AgentScope with `scoped_user_id = tenant_id:user_id`.
- Phase 2: Workspace, mock tools, permission checks, and audit logs were added at the platform layer.
- Phase 2.1: Tool Permission Admin API, workspace files/cleanup, tool timeout, `slow_tool`, and structured audit/tracing were added.
- Phase 2.2: AgentScope native Tool / Permission / Workspace alignment was documented.
- Phase 2.3.1: Tool Registry metadata gained `native_type`, `native_ref`, `enabled`, and `timeout_seconds`.

Current platform tool invocation at `/api/platform/tools/{tool_name}/invoke` is platform active invocation. It is not Agent runtime automatic tool calling during `/chat`.

The goal of Phase 2.3.2 is to verify AgentScope 2.0.3 runtime extension signatures and design a future `extra_agent_tools` adapter. This phase does not implement the adapter.

Official references:

- Agent Service: https://docs.agentscope.io/versions/2.0.3/zh/deploy/agent-service
- Tool: https://docs.agentscope.io/versions/2.0.3/zh/building-blocks/tool
- Permission System: https://docs.agentscope.io/versions/2.0.3/zh/building-blocks/permission-system
- Workspace: https://docs.agentscope.io/versions/2.0.3/zh/building-blocks/workspace

## 2. Verified AgentScope 2.0.3 API Signatures

Local verification command:

```powershell
conda run -n agent-platform python -c "import agentscope; print(getattr(agentscope, '__version__', 'unknown')); print(agentscope.__file__)"
```

Result:

```text
agentscope version: 2.0.3
agentscope file: D:\ana\envs\agent-platform\Lib\site-packages\agentscope\__init__.py
```

### create_app

Verified import:

```python
from agentscope.app import create_app
```

Verified signature:

```text
(storage: agentscope.app.storage._base.StorageBase,
 message_bus: agentscope.app.message_bus._base.MessageBus,
 workspace_manager: agentscope.app.workspace_manager._base.WorkspaceManagerBase,
 knowledge_base_manager: agentscope.app.rag.knowledge_base_manager._base.KnowledgeBaseManagerBase | None = None,
 knowledge_parsers: list[agentscope.rag._parser._base.ParserBase] | dict[str, agentscope.rag._parser._base.ParserBase] | None = None,
 knowledge_chunker: agentscope.rag._chunker._base.ChunkerBase | None = None,
 blob_store: agentscope.app.rag.blob_store._base.BlobStoreBase | None = None,
 enable_index_worker: bool = True,
 *,
 extra_credentials: list[type[agentscope.credential._base.CredentialBase]] | None = None,
 extra_middlewares: list[Any] | None = None,
 extra_agent_middlewares: Callable[[str, str, str], Awaitable[list[agentscope.middleware._base.MiddlewareBase]]] | None = None,
 extra_agent_tools: Callable[[str, str, str], Awaitable[list[agentscope.tool._base.ToolBase]]] | None = None,
 custom_subagent_templates: list[agentscope.app._types.SubAgentTemplate] | None = None,
 custom_agent_cls: type[agentscope.agent._agent.Agent] | None = None,
 title: str = "AgentScope",
 version: str = "2.0.3") -> Any
```

`extra_agent_tools` exists and is a three-argument async factory:

```text
Callable[[str, str, str], Awaitable[list[agentscope.tool._base.ToolBase]]]
```

The three arguments are `user_id`, `agent_id`, and `session_id`.

`extra_agent_middlewares` exists and is a three-argument async factory:

```text
Callable[[str, str, str], Awaitable[list[agentscope.middleware._base.MiddlewareBase]]]
```

### AgentToolFactory And AgentMiddlewareFactory

Verified import:

```python
from agentscope.app._types import AgentToolFactory, AgentMiddlewareFactory
```

Verified values:

```text
AgentToolFactory = Callable[[str, str, str], Awaitable[list[agentscope.tool._base.ToolBase]]]
AgentMiddlewareFactory = Callable[[str, str, str], Awaitable[list[agentscope.middleware._base.MiddlewareBase]]]
```

### ChatService And Toolkit Assembly

Verified source behavior in `agentscope.app._service._chat.ChatService`:

- `extra_agent_middlewares(user_id, agent_id, session_id)` is awaited during chat assembly.
- `extra_agent_tools` is passed into `get_toolkit(...)` as `extra_factory`.

Verified source behavior in `agentscope.app._service._toolkit.get_toolkit`:

```python
if extra_factory is not None:
    tools += await extra_factory(
        user_id,
        agent_record.id,
        session_record.id,
    )

return Toolkit(
    tools=tools,
    skills_or_loaders=await workspace.list_skills(),
    mcps=await workspace.list_mcps(),
    tool_groups=tool_groups,
)
```

Conclusion: the adapter should keep the signature:

```python
async def build_extra_agent_tools(
    user_id: str,
    agent_id: str,
    session_id: str,
) -> list[ToolBase]:
    ...
```

### ToolBase / FunctionTool / Toolkit

Verified imports:

```python
from agentscope.tool import ToolBase, FunctionTool, Toolkit
```

Actual modules:

```text
ToolBase     -> agentscope.tool._base.ToolBase
FunctionTool -> agentscope.tool._adapters.FunctionTool
Toolkit      -> agentscope.tool._toolkit.Toolkit
```

Verified signatures:

```text
ToolBase(middlewares: list[ToolMiddlewareBase] | None = None) -> None
```

```text
FunctionTool(
    func: Callable[..., ToolChunk | Awaitable[ToolChunk] | Generator | AsyncGenerator | Coroutine],
    name: str | None = None,
    description: str | None = None,
    is_concurrency_safe: bool = True,
    is_read_only: bool = False,
    is_state_injected: bool = False,
    middlewares: list[ToolMiddlewareBase] | None = None,
) -> None
```

```text
Toolkit(
    tools: list[ToolBase] | None = None,
    skills_or_loaders: Sequence[str | Skill | SkillLoaderBase] | None = None,
    mcps: list[MCPClient] | None = None,
    tool_groups: list[ToolGroup] | None = None,
    meta_tool_response_template: str = ...,
    skill_instruction_template: str = ...,
) -> None
```

Important source finding: `FunctionTool.check_permissions` defaults to `ASK`, with the message that custom function tools must be explicitly allowed by the user. Therefore, future adapter work must not rely only on injection filtering. Runtime permission context or a wrapper/tool-level check is still required.

### MiddlewareBase

Verified import:

```python
from agentscope.middleware import MiddlewareBase
```

Actual module:

```text
agentscope.middleware._base.MiddlewareBase
```

Verified signature:

```text
MiddlewareBase() -> None
```

Verified hooks include:

- `on_reply`
- `on_reasoning`
- `on_acting`
- `on_model_call`
- `on_system_prompt`
- `on_compress_context`
- `list_tools`

Important source finding: `on_acting` wraps the raw `toolkit.call_tool` execution. AgentScope source comments say permission checking, input validation, and context writes are handled outside this hook. This makes `on_acting` useful for runtime audit/tracing, but not sufficient as the only permission boundary.

### PermissionRule / PermissionContext

Verified imports:

```python
from agentscope.permission import PermissionRule, PermissionContext
from agentscope.permission import PermissionMode, PermissionBehavior
```

Actual modules:

```text
PermissionRule    -> agentscope.permission._rule.PermissionRule
PermissionContext -> agentscope.permission._context.PermissionContext
```

Verified signatures:

```text
PermissionRule(
    *,
    tool_name: str,
    rule_content: str | None,
    behavior: agentscope.permission._types.PermissionBehavior,
    source: str,
) -> None
```

Verified fields:

```text
tool_name: str
rule_content: str | None
behavior: PermissionBehavior
source: str
```

```text
PermissionContext(
    *,
    mode: agentscope.permission._types.PermissionMode = PermissionMode.DEFAULT,
    working_directories: dict[str, AdditionalWorkingDirectory] = {},
    allow_rules: dict[str, list[PermissionRule]] = {},
    deny_rules: dict[str, list[PermissionRule]] = {},
    ask_rules: dict[str, list[PermissionRule]] = {},
) -> None
```

Verified behavior values:

```text
PermissionBehavior.ALLOW = "allow"
PermissionBehavior.DENY  = "deny"
PermissionBehavior.ASK   = "ask"
```

Verified mode values from source:

```text
PermissionMode.DEFAULT
PermissionMode.EXPLORE
PermissionMode.ACCEPT_EDITS
PermissionMode.BYPASS
PermissionMode.DONT_ASK
```

### WorkspaceManager / LocalWorkspaceManager

Verified imports:

```python
from agentscope.app.workspace_manager import WorkspaceManagerBase, LocalWorkspaceManager
```

Actual modules:

```text
WorkspaceManagerBase  -> agentscope.app.workspace_manager._base.WorkspaceManagerBase
LocalWorkspaceManager -> agentscope.app.workspace_manager._local_workspace_manager.LocalWorkspaceManager
```

Verified signatures:

```text
WorkspaceManagerBase() -> None
```

```text
LocalWorkspaceManager(
    basedir: str,
    default_mcps: list | None = None,
    skill_paths: list[str] | None = None,
    ttl: float = 3600.0,
) -> None
```

### Failed Or Rejected Import Paths

These guessed paths are not valid in the installed AgentScope 2.0.3 package:

```text
agentscope.tool._function_tool
agentscope.permission._permission
agentscope.app.workspace_manager._workspace_manager
```

Use the verified public imports above instead.

## 3. Current Platform Tool Registry

Phase 2.3.1 tool metadata:

- `tool_name`
- `description`
- `native_type`
- `native_ref`
- `timeout_seconds`
- `enabled`
- `input_schema`
- `default_timeout_seconds`

Current mock tools:

- `echo_tool`
- `time_tool`
- `slow_tool`

Current properties:

- `native_type=mock`
- `native_ref=null`
- `enabled=true`

Current platform invoke API:

```text
POST /api/platform/tools/{tool_name}/invoke
```

This endpoint is platform active invocation for admin testing, smoke tests, and management-side calls. It is not Agent runtime automatic tool calling during `/chat`.

## 4. extra_agent_tools Adapter Design Goals

Future adapter goals:

- Read platform Tool Registry metadata.
- Decide dynamically by `tenant_id`, `user_id`, `agent_id`, and `session_id`.
- Inject only `enabled=true` tools.
- Inject only permission-allowed tools. Default deny remains the platform baseline.
- Handle `native_type=mock`, `agentscope_tool`, `mcp`, and `skill` differently.
- Preserve Phase 2.1 permission, audit, and tracing semantics.
- Prevent Agent runtime from bypassing platform governance.
- Keep `/api/platform/tools/{tool_name}/invoke` as a separate platform active invocation API.

Important context issue: AgentScope only passes `user_id`, `agent_id`, and `session_id` into `extra_agent_tools`. In this platform, `user_id` is expected to be the scoped value `tenant_id:user_id` when called from the platform facade. The adapter must parse or resolve tenant/user context from that scoped user id or from future platform storage.

## 5. native_type Mapping Strategy

### native_type=mock

Current mock tools remain platform-owned test tools.

Phase 2.3.2 does not recommend injecting mock tools into runtime by default. If a later smoke test needs runtime injection, only safe mock tools may be injected:

- no shell execution
- no system commands
- no file deletion
- no real enterprise systems
- bounded timeout
- explicit allow permission

### native_type=agentscope_tool

`native_ref` should point to an AgentScope-native tool name or import path.

Future adapter behavior:

- Resolve `native_ref`.
- Construct an AgentScope `ToolBase` instance or `FunctionTool`.
- Attach platform permission/tracing wrapper or middleware.
- Reject unknown or unsafe native refs.

Need later source verification for each concrete tool constructor. `FunctionTool` itself is verified, but specific built-in tool constructors must be verified before use.

### native_type=mcp

`native_ref` should point to an MCP server or MCP tool identity.

Phase 2.3.2 does not connect MCP.

Before enabling MCP:

- define parameter schema
- define tenant/user/agent permission policy
- define timeout behavior
- define audit/tracing records
- define workspace and secret boundaries
- block unsafe tools by default

### native_type=skill

`native_ref` should point to an AgentScope Skill name or path.

Phase 2.3.2 does not load skills.

Before enabling skills:

- define skill catalog
- verify skill directory lifecycle
- ensure workspace isolation
- define permission model
- define audit/tracing surface

AgentScope source confirms skills are not directly called like tools. The skill viewer lets the agent read skill instructions, then the agent uses available tools to act.

## 6. Adapter Pseudocode

The pseudocode below follows the verified AgentScope signature:

```python
async def build_extra_agent_tools(
    user_id: str,
    agent_id: str,
    session_id: str,
) -> list[ToolBase]:
    tenant_id, real_user_id = parse_scoped_user_id(user_id)
    scoped_user = ScopedUser(
        tenant_id=tenant_id,
        user_id=real_user_id,
        scoped_user_id=user_id,
    )

    platform_tools = list_registered_tools()
    native_tools: list[ToolBase] = []

    for tool in platform_tools:
        if not tool.enabled:
            continue

        if not is_tool_allowed(settings, scoped_user, agent_id, tool.name):
            continue

        if tool.native_type == "mock":
            # Phase 2.3.2 design recommendation:
            # keep mock tools out of runtime unless a later smoke phase
            # explicitly enables safe mock injection.
            continue

        if tool.native_type == "agentscope_tool":
            native_tools.append(
                build_agentscope_tool_from_ref(
                    native_ref=tool.native_ref,
                    tenant_id=tenant_id,
                    user_id=real_user_id,
                    agent_id=agent_id,
                    session_id=session_id,
                    timeout_seconds=tool.timeout_seconds,
                ),
            )
            continue

        if tool.native_type == "mcp":
            native_tools.append(
                build_mcp_tool_from_ref(
                    native_ref=tool.native_ref,
                    tenant_id=tenant_id,
                    user_id=real_user_id,
                    agent_id=agent_id,
                    session_id=session_id,
                ),
            )
            continue

        if tool.native_type == "skill":
            native_tools.extend(
                build_skill_tools_from_ref(
                    native_ref=tool.native_ref,
                    tenant_id=tenant_id,
                    user_id=real_user_id,
                    agent_id=agent_id,
                    session_id=session_id,
                ),
            )

    return native_tools
```

Runtime audit/tracing can be designed in two layers:

```python
async def build_extra_agent_middlewares(
    user_id: str,
    agent_id: str,
    session_id: str,
) -> list[MiddlewareBase]:
    tenant_id, real_user_id = parse_scoped_user_id(user_id)
    return [
        RuntimeToolAuditMiddleware(
            tenant_id=tenant_id,
            user_id=real_user_id,
            scoped_user_id=user_id,
            agent_id=agent_id,
            session_id=session_id,
        ),
    ]
```

Do not implement this in Phase 2.3.2.

## 7. Permission Alignment Design

Current platform permission protects only:

```text
POST /api/platform/tools/{tool_name}/invoke
```

Future runtime permission must protect:

```text
Agent automatic tool calls during /chat
```

Design:

- Platform permission JSON remains the enterprise policy source.
- Default deny remains unchanged.
- `extra_agent_tools` adapter injects only allowed tools.
- Runtime tool calling still needs a second permission boundary.
- Phase 2.3.3 or 2.3.4 should map platform rules to AgentScope `PermissionRule`.
- `PermissionContext.allow_rules`, `deny_rules`, and `ask_rules` should be generated from platform policies.
- ASK mode is not enabled for the enterprise platform yet. Use allow/deny first.
- Since `FunctionTool.check_permissions` defaults to ASK, the mapper must explicitly allow approved tools or provide a safe wrapper.

Injection filtering is not enough. A tool could be injected correctly but later called with unsafe arguments. Runtime permission should evaluate both tool identity and call input.

## 8. Audit / Tracing Alignment Design

Current audit/tracing covers platform invoke.

Future runtime tool calling must also record:

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

Design:

- Use `extra_agent_middlewares` to return runtime audit/tracing middleware.
- `MiddlewareBase.on_acting` is the likely hook for recording actual tool execution duration and result.
- Because AgentScope source says permission checking occurs outside `on_acting`, permission decisions may need to be recorded through a permission mapper or tool wrapper as well.
- Tool wrappers may be useful for timeout and tool-specific tracing.
- Phase 2.3.2 only documents this design.
- Phase 2.3.5 should implement runtime audit middleware after a minimal adapter exists.

## 9. Workspace Alignment Design

Runtime tools should use the platform isolation path:

```text
{WORKSPACE_BASEDIR}/{tenant_id}/{user_id}/{agent_id}/{session_id}
```

Design:

- Adapter-created tools should receive workspace context when the tool needs filesystem access.
- Tools that do not need filesystem access should not receive broad workspace privileges.
- A future custom WorkspaceManager should make AgentScope runtime use the same path policy as platform workspace APIs.
- Phase 2.3.2 does not implement custom WorkspaceManager.
- Phase 2.3.4 or Phase 2.3.6 should verify and align `WorkspaceManagerBase.get_workspace` behavior.

## 10. Compatibility With Existing APIs

The adapter is a runtime injection path. It does not replace platform APIs.

Compatibility commitments:

- Do not delete `GET /api/platform/tools`.
- Do not delete `POST /api/platform/tools/{tool_name}/invoke`.
- Do not change the invoke request body.
- Do not change Phase 1.5 chat/session/message APIs.
- Do not change Phase 2.1 Tool Permission Admin API.
- Keep AgentScope native APIs available for low-level debugging.
- Keep `/api/platform/tools/{tool_name}/invoke` for smoke tests, platform active invocation, and management-side debugging.

## 11. Risks And Security Boundaries

- AgentScope 2.0.3 source and documentation can diverge. Verify exact constructors before implementation.
- `extra_agent_tools` receives `user_id`, `agent_id`, and `session_id`; it does not receive explicit `tenant_id`. The platform must parse scoped user id or design a stronger context lookup.
- Filtering permissions only at injection time is not enough. Runtime call input still needs permission checks.
- MCP and Skills are higher risk than simple mock tools and must include schema, permission, timeout, audit, and workspace boundaries.
- Do not connect shell, system-command, file-delete, or destructive filesystem tools.
- Runtime audit middleware may affect chat latency.
- Custom WorkspaceManager may affect AgentScope workspace lifecycle, TTL, MCP process lifecycle, and session reuse.
- JSON permission files still have concurrency-write risk and are not production policy storage.
- FunctionTool defaults to ASK permission behavior; enterprise runtime must explicitly map allow/deny policy.

## 12. Phase 2.3.3 Implementation Recommendation

Recommended small steps:

1. Phase 2.3.3: Implement a minimal adapter skeleton, but keep it disabled or return empty by default until smoke settings are explicit.
2. Phase 2.3.3 option A: Support only `native_type=mock` for a safe smoke tool, with explicit allow and no shell/system/file-delete behavior.
3. Phase 2.3.3 option B: Support only a verified safe `agentscope_tool` after constructor-level source verification.
4. Phase 2.3.4: Implement permission mapper and runtime second-check strategy.
5. Phase 2.3.5: Implement runtime audit middleware using `extra_agent_middlewares`.
6. Phase 2.3.6: Design or implement custom WorkspaceManager alignment.
7. Phase 2.3.7: Run local smoke tests.
8. Phase 2.3.8: Sync through GitHub and run ECS smoke tests.

If AgentScope runtime tool constructor details are unclear for a chosen tool, do not implement it. Add another verification step first.

## 13. Future Smoke Test Design

Future runtime adapter smoke tests should verify:

- `GET /api/platform/tools` still returns native metadata.
- Create an allow rule with Tool Permission Admin API.
- Agent chat can see and call an injected safe tool.
- A not-allowed tool is not injected or is rejected at runtime.
- Runtime tool calls write audit/tracing records.
- Records include `trace_id`, `status`, `duration_ms`, and `error_code`.
- `tenantA:userA` and `tenantB:userA` receive isolated tool injection.
- Phase 1.5 chat/message behavior remains unchanged for normal sessions.
- Platform invoke API still works independently from Agent runtime tool calling.

## 14. Acceptance Criteria

- `docs/phase2_3_2-extra-agent-tools-adapter-design.md` exists.
- The document includes AgentScope 2.0.3 signature verification results.
- The document clearly separates platform invoke API from runtime tool calling.
- The document describes `extra_agent_tools` adapter design.
- The document describes permission, audit/tracing, and workspace alignment.
- The document proposes Phase 2.3.3 next steps.
- No ECS files are changed.
- No official AgentScope source code is changed.
- No real `.env` file is touched.
- No existing APIs are broken.

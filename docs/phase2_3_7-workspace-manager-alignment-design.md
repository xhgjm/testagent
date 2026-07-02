# Phase 2.3.7: WorkspaceManager Alignment Design

## Goal

This document compares AgentScope 2.0.3 `WorkspaceManager` behavior with the
platform workspace resolver. It is a design document only.

Phase 2.3.7 does not implement a custom `WorkspaceManager`, does not replace
AgentScope `LocalWorkspaceManager`, and does not change the chat/session/message
runtime path.

## Verified AgentScope 2.0.3 Signatures

Local environment:

```text
agentscope version: 2.0.3
agentscope file: D:\ana\envs\agent-platform\Lib\site-packages\agentscope\__init__.py
```

Verified `create_app` import:

```python
from agentscope.app import create_app
```

Verified signature:

```text
create_app(
    storage: StorageBase,
    message_bus: MessageBus,
    workspace_manager: WorkspaceManagerBase,
    knowledge_base_manager=None,
    knowledge_parsers=None,
    knowledge_chunker=None,
    blob_store=None,
    enable_index_worker=True,
    *,
    extra_credentials=None,
    extra_middlewares=None,
    extra_agent_middlewares=None,
    extra_agent_tools=None,
    custom_subagent_templates=None,
    custom_agent_cls=None,
    title="AgentScope",
    version="2.0.3",
) -> Any
```

Conclusion: `create_app` requires a `workspace_manager` positional argument.

## Verified WorkspaceManagerBase

Verified import:

```python
from agentscope.app.workspace_manager import WorkspaceManagerBase
```

Verified class:

```text
agentscope.app.workspace_manager._base.WorkspaceManagerBase
```

Verified constructor:

```text
WorkspaceManagerBase() -> None
```

Verified methods:

```text
create_workspace(self, user_id: str, agent_id: str, session_id: str) -> WorkspaceBase
get_workspace(self, user_id: str, agent_id: str, session_id: str, workspace_id: str) -> WorkspaceBase
close(self, workspace_id: str) -> None
close_all(self) -> None
```

## Verified LocalWorkspaceManager

Verified import:

```python
from agentscope.app.workspace_manager import LocalWorkspaceManager
```

Verified class:

```text
agentscope.app.workspace_manager._local_workspace_manager.LocalWorkspaceManager
```

Verified constructor:

```text
LocalWorkspaceManager(
    basedir: str,
    default_mcps: list | None = None,
    skill_paths: list[str] | None = None,
    ttl: float = 3600.0,
) -> None
```

Verified methods:

```text
create_workspace(self, user_id: str, agent_id: str, session_id: str) -> LocalWorkspace
get_workspace(self, user_id: str, agent_id: str, session_id: str, workspace_id: str) -> LocalWorkspace
close(self, workspace_id: str) -> None
close_all(self) -> None
```

## LocalWorkspaceManager Semantics

Source inspection shows:

- `basedir` is converted to an absolute path.
- `default_mcps` are seeded into brand-new workspaces.
- `skill_paths` are seeded into brand-new workspaces.
- `ttl` evicts idle cached workspace objects.
- workspaces are cached by `workspace_id`.
- expired workspaces are closed outside the manager lock.
- `create_workspace(...)` accepts `user_id` and `session_id` for interface
  parity, but the local workdir is currently:

```text
basedir / agent_id
```

- `get_workspace(...)` reconstructs the same deterministic local workdir:

```text
basedir / agent_id
```

Important consequence: AgentScope local workspace path isolation is agent-level
in this implementation, not tenant/user/session-level.

## Current main.py Integration

Current platform backend already passes a workspace manager to AgentScope:

```python
workspace_manager = LocalWorkspaceManager(
    basedir=settings.workspace_basedir,
    ttl=float(settings.workspace_ttl_seconds),
)

app = create_agentscope_app(
    storage=storage,
    message_bus=message_bus,
    workspace_manager=workspace_manager,
    ...
)
```

Therefore Phase 1 is correctly integrated with AgentScope Agent Service. Phase
2.3.7 does not change this.

## Platform Workspace Resolver Semantics

The platform resolver lives in:

```text
backend/app/platform/workspace.py
backend/app/platform/runtime_workspace.py
```

The platform path policy is:

```text
WORKSPACE_BASEDIR / tenant_id / user_id / agent_id / session_id
```

The resolver:

- sanitizes each path segment
- resolves the final path
- verifies that the final path stays under `WORKSPACE_BASEDIR`
- can create the session workspace directory
- is used by `/api/platform/workspaces/resolve`
- is reused by runtime workspace alignment for `runtime_echo_tool`

## Boundary Comparison

| Area | AgentScope LocalWorkspaceManager | Platform Workspace Resolver |
| --- | --- | --- |
| Primary lifecycle | AgentScope runtime workspace lifecycle | Platform tenant/session workspace path policy |
| Path shape | `basedir/agent_id` | `basedir/tenant_id/user_id/agent_id/session_id` |
| Uses tenant id | No direct tenant parameter | Yes |
| Uses user id | Accepted, but local path does not use it | Yes |
| Uses session id | Accepted, but local path does not use it | Yes |
| Cache key | `workspace_id` | No runtime object cache |
| TTL | Idle workspace object eviction | Cleanup helpers are platform-owned |
| MCP | `default_mcps` seeded into workspace | Reserved, not connected |
| Skill | `skill_paths` seeded into workspace | Reserved, not connected |
| Audit traceability | Not audit-specific | workspace path recorded in runtime audit |

## Should We Implement A Custom WorkspaceManager Now?

Recommendation: no, not in Phase 2.3.7.

Reasons:

- AgentScope workspace lifecycle is tied to `workspace_id`, cache eviction,
  MCP startup/shutdown, and Skill loading.
- Replacing `workspace_manager` can affect native session behavior.
- LocalWorkspaceManager currently uses `basedir/agent_id`; changing it without
  broader tests may affect existing AgentScope assumptions.
- Runtime tools remain experimental and default closed.
- MCP and Skills are not enabled, so there is no immediate need to remap their
  workspace paths.
- Platform resolver already provides a tenant/session-scoped governance context
  for platform APIs and the safe runtime smoke tool.

## Future Minimal Design: PlatformWorkspaceManager

If later phases require full alignment, introduce a small class:

```python
class PlatformWorkspaceManager(WorkspaceManagerBase):
    async def create_workspace(
        self,
        user_id: str,
        agent_id: str,
        session_id: str,
    ) -> WorkspaceBase:
        ...

    async def get_workspace(
        self,
        user_id: str,
        agent_id: str,
        session_id: str,
        workspace_id: str,
    ) -> WorkspaceBase:
        ...

    async def close(self, workspace_id: str) -> None:
        ...

    async def close_all(self) -> None:
        ...
```

Design requirements:

- parse `user_id` as platform `tenant_id:user_id`
- reuse the platform workspace resolver
- never bypass tenant/user/agent/session isolation
- preserve `workspace_id` cache semantics
- preserve `default_mcps` and `skill_paths` behavior if MCP/Skill are enabled
- preserve TTL cleanup semantics
- keep path traversal protections
- preserve audit traceability
- fail closed if scoped user id is invalid

## Risks

- Replacing `workspace_manager` may change AgentScope native session lifecycle.
- MCP and Skill loading may depend on AgentScope workspace conventions.
- Path traversal and tenant escape risks increase if resolver and manager drift.
- Cleanup may race with active runtime tool execution.
- TTL object eviction is different from deleting workspace files.
- JSON audit and permission files are not production-grade concurrent storage.
- A custom manager would need ECS smoke tests for chat, SSE, messages, MCP/Skill
  disabled behavior, and workspace cleanup.

## Phase Recommendations

Phase 2.3.7:

- keep this as design and regression only
- do not change `backend/app/main.py`
- do not replace `LocalWorkspaceManager`
- keep runtime tools and runtime audit default closed

Phase 2.4:

- close Phase 2 platform foundation
- add focused tests and smoke scripts
- review docs and operational checklist
- keep custom WorkspaceManager as design until needed

Phase 3:

- start RAG through platform facade plus AgentScope RAG Service
- do not begin RAG by replacing WorkspaceManager
- revisit workspace manager alignment only if RAG indexing, MCP, or Skills need
  runtime-local workspace lifecycle integration

# Phase 2.3.3: extra_agent_tools Adapter Skeleton

## Goal

Phase 2.3.3 adds a minimal `extra_agent_tools` adapter skeleton based on the AgentScope 2.0.3 signatures verified in Phase 2.3.2.

This is intentionally conservative:

- Runtime tools are disabled by default.
- The adapter returns `[]` unless explicitly enabled by configuration.
- Only one safe mock runtime tool is prepared: `runtime_echo_tool`.
- MCP, Skills, real enterprise systems, shell commands, system commands, file deletion, network access, RAG, Memory, Team, and frontend are out of scope.

## What Was Implemented

New module:

```text
backend/app/platform/runtime_tools.py
```

It provides:

```python
async def build_extra_agent_tools(
    user_id: str,
    agent_id: str,
    session_id: str,
) -> list[ToolBase]:
    ...
```

The signature matches AgentScope `create_app(extra_agent_tools=...)`:

```text
Callable[[str, str, str], Awaitable[list[ToolBase]]]
```

The existing `backend/app/tools/factory.py` delegates to this adapter. `backend/app/main.py` already passes `build_extra_agent_tools` into `create_app`, so the integration point remains stable.

## New Configuration

`.env.example` now includes:

```env
PLATFORM_ENABLE_RUNTIME_TOOLS=false
PLATFORM_RUNTIME_TOOLS_MODE=disabled
```

Defaults:

- `PLATFORM_ENABLE_RUNTIME_TOOLS=false`
- `PLATFORM_RUNTIME_TOOLS_MODE=disabled`

Default behavior is unchanged from Phase 2.3.1: no runtime tools are injected.

Supported experimental modes:

- `disabled`: always return `[]`
- `mock`
- `mock_safe`
- `runtime_echo`

Only the safe `runtime_echo_tool` can be injected in the non-disabled modes, and only after permission allow.

## Safe Runtime Echo Tool

The skeleton can build an AgentScope `FunctionTool`:

```text
runtime_echo_tool
```

Behavior:

- accepts `text`
- returns the same text
- does not read files
- does not write files
- does not delete files
- does not access network
- does not execute commands
- does not read environment variables
- does not call real enterprise systems

The platform Tool Registry also exposes `runtime_echo_tool` as a safe mock tool so metadata and permission rules can be managed consistently.

## Permission Behavior

Default deny remains unchanged.

The adapter injects `runtime_echo_tool` only when all conditions are true:

- `PLATFORM_ENABLE_RUNTIME_TOOLS=true`
- `PLATFORM_RUNTIME_TOOLS_MODE` is one of `mock`, `mock_safe`, or `runtime_echo`
- the incoming AgentScope `user_id` can be parsed as `tenant_id:user_id`
- `runtime_echo_tool` is registered and enabled
- platform permission JSON explicitly allows the current `tenant_id`, `user_id`, `agent_id`, and `tool_name=runtime_echo_tool`

This phase only performs injection-time filtering. It does not implement AgentScope `PermissionRule` mapping and does not implement runtime second permission checks. Those are required before production usage.

## Audit / Tracing Behavior

This phase does not implement runtime tool-call audit/tracing JSONL records.

The adapter may write normal debug/info logs when it is called, disabled, denied, or injecting a safe mock tool. Full runtime tool audit/tracing is reserved for Phase 2.3.5.

## Platform Invoke API vs Runtime Tool Calling

These are separate paths:

- `POST /api/platform/tools/{tool_name}/invoke`: platform active invocation for admin testing and management-side calls.
- `extra_agent_tools`: AgentScope runtime injection path used when Agent chat assembles its toolkit.

Phase 2.3.3 keeps both paths compatible. It does not remove or rename any existing platform API.

## Why MCP And Skills Are Not Enabled

MCP and Skills are higher-risk runtime extension paths because they require:

- parameter schema governance
- tenant/user/agent permission rules
- timeout controls
- audit/tracing
- workspace isolation
- secret handling
- lifecycle management

This phase only proves that the platform can safely wire an adapter skeleton without changing existing chat behavior.

## Local Smoke Test

### 1. Syntax Check

```powershell
conda run -n agent-platform python -m compileall backend\app
```

### 2. Default Adapter Returns Empty

```powershell
conda run -n agent-platform python -c "import asyncio; from backend.app.platform.runtime_tools import build_extra_agent_tools; print(asyncio.run(build_extra_agent_tools('tenantA:userA','agentSmoke','sessionSmoke')))"
```

Expected:

```text
[]
```

### 3. Enabled But No Permission Still Returns Empty

Use a temporary permission file with no allow rule:

```powershell
$env:PLATFORM_ENABLE_RUNTIME_TOOLS="true"
$env:PLATFORM_RUNTIME_TOOLS_MODE="runtime_echo"
$env:PLATFORM_TOOL_PERMISSION_FILE="tmp/runtime-tools-permissions.json"
conda run -n agent-platform python -c "import asyncio; from backend.app.config import get_settings; get_settings.cache_clear(); from backend.app.platform.runtime_tools import build_extra_agent_tools; print(asyncio.run(build_extra_agent_tools('tenantA:userA','agentSmoke','sessionSmoke')))"
```

Expected:

```text
[]
```

### 4. Enabled And Allowed Returns runtime_echo_tool

Create `tmp/runtime-tools-permissions.json`:

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

Then run:

```powershell
$env:PLATFORM_ENABLE_RUNTIME_TOOLS="true"
$env:PLATFORM_RUNTIME_TOOLS_MODE="runtime_echo"
$env:PLATFORM_TOOL_PERMISSION_FILE="tmp/runtime-tools-permissions.json"
conda run -n agent-platform python -c "import asyncio; from backend.app.config import get_settings; get_settings.cache_clear(); from backend.app.platform.runtime_tools import build_extra_agent_tools; tools=asyncio.run(build_extra_agent_tools('tenantA:userA','agentSmoke','sessionSmoke')); print([tool.name for tool in tools])"
```

Expected:

```text
['runtime_echo_tool']
```

### 5. Tool Metadata Still Works

Start backend:

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8891 --reload
```

Check:

```bash
curl -s \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  http://127.0.0.1:8891/api/platform/tools \
  | python -m json.tool
```

Expected: `runtime_echo_tool` appears with `native_type=mock`, `native_ref=null`, `enabled=true`, and `timeout_seconds`.

### 6. Existing Chat / Session / Message Flow

With default runtime tools disabled, Phase 1.5 chat/session/message smoke tests should behave exactly as before. Use [phase1_5-platform-api.md](phase1_5-platform-api.md).

This phase does not require proving that a model automatically calls the injected tool during chat. That belongs to a later, explicitly enabled runtime smoke phase.

## ECS Smoke Test

After commit and push:

```bash
cd /app/agent-platform
git pull
source .venv/bin/activate
python -m compileall backend/app
```

Confirm `.env` keeps runtime tools disabled unless you are intentionally testing:

```env
PLATFORM_ENABLE_RUNTIME_TOOLS=false
PLATFORM_RUNTIME_TOOLS_MODE=disabled
```

Restart backend on port `8891` and verify:

```bash
curl -s http://127.0.0.1:8891/platform/health | python -m json.tool
curl -s -H "X-Tenant-ID: tenantA" -H "X-User-ID: userA" \
  http://127.0.0.1:8891/api/platform/tools | python -m json.tool
```

Then reuse the Phase 1.5 smoke test to confirm chat/session/message behavior is unchanged.

## Risks And Limits

- This is not a production runtime tool permission boundary.
- Injection-time filtering is not enough; runtime second permission checks are still needed.
- AgentScope `FunctionTool` defaults to ASK permission behavior, so Phase 2.3.4 must map platform allow/deny into AgentScope permission context or provide a safe wrapper.
- Runtime tool calls do not yet write `tool-calls-audit.jsonl`.
- MCP and Skills remain disabled.
- The adapter only receives `user_id`, `agent_id`, and `session_id`; tenant/user are parsed from scoped `tenant_id:user_id`.
- JSON permission files are still not production-grade concurrent policy storage.

## Next Step: Phase 2.3.4

Recommended next phase:

- Implement platform permission rule to AgentScope `PermissionRule` mapper.
- Add runtime second permission check.
- Keep ASK mode disabled for enterprise backend usage.
- Preserve default deny.
- Continue avoiding MCP, Skills, shell, system commands, file deletion, and real enterprise tools until governance is complete.


## ECS Smoke Test Result

Date: 2026-07-01
Port: 8891
Result: Passed

Verified:
- Existing chat/session/message flow still works when runtime tools are disabled.
- Default configuration keeps PLATFORM_ENABLE_RUNTIME_TOOLS=false and PLATFORM_RUNTIME_TOOLS_MODE=disabled.
- build_extra_agent_tools returns [] by default.
- runtime_echo_tool is visible in /api/platform/tools metadata.
- runtime_echo_tool is a safe mock tool only.
- With PLATFORM_ENABLE_RUNTIME_TOOLS=true and PLATFORM_RUNTIME_TOOLS_MODE=mock, adapter still requires permission allow.
- After adding explicit allow for runtime_echo_tool, build_extra_agent_tools returns runtime_echo_tool.
- Without explicit runtime enablement, adapter returns [] even if allow rule exists.
- No MCP, Skill, shell, file deletion, network access, or enterprise system integration is enabled.

Conclusion:
Phase 2.3.3 extra_agent_tools adapter skeleton passed ECS smoke test.
# Phase 2.3.1: Tool Metadata Native Alignment

## Goal

Phase 2.3.1 adds AgentScope native alignment metadata to the platform Tool Registry. This is a low-risk metadata-only step. It does not connect real AgentScope runtime tool calling, does not implement an `extra_agent_tools` adapter, and does not add any dangerous tools.

## What Changed

`GET /api/platform/tools` now returns native alignment fields for each platform tool:

- `tool_name`
- `description`
- `native_type`: `mock`, `agentscope_tool`, `mcp`, or `skill`
- `native_ref`
- `timeout_seconds`
- `enabled`

For compatibility, the response also keeps existing fields such as `name`, `input_schema`, and `default_timeout_seconds`.

Current tools:

| Tool | native_type | native_ref | enabled | Purpose |
| --- | --- | --- | --- | --- |
| `echo_tool` | `mock` | `null` | `true` | Echo JSON arguments for safe smoke tests |
| `time_tool` | `mock` | `null` | `true` | Return current UTC time |
| `slow_tool` | `mock` | `null` | `true` | Trigger timeout behavior safely |

## Compatibility

`POST /api/platform/tools/{tool_name}/invoke` is unchanged:

- Same request body.
- Same default-deny permission model.
- Same explicit allow behavior.
- Same timeout behavior.
- Same audit JSONL records.
- Same structured tracing fields.

Phase 1.5 chat, session, message, and native AgentScope APIs are not changed.

## Boundary

This phase does not implement:

- `extra_agent_tools` adapter
- AgentScope `PermissionRule` mapper
- Custom WorkspaceManager
- Runtime audit middleware
- RAG
- Long-term Memory
- Agent Team
- Frontend
- Real enterprise tools
- Shell or system command tools

The current platform tool invoke API is still platform active invocation. Agent automatic tool calling during chat is a later Phase 2.3 step.

## Local Smoke Test

Start the backend locally:

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8891 --reload
```

Check tool metadata:

```bash
curl -s \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  http://127.0.0.1:8891/api/platform/tools \
  | python -m json.tool
```

Expected: each tool includes `tool_name`, `native_type`, `native_ref`, `timeout_seconds`, and `enabled`. The current mock tools should show `native_type=mock` and `native_ref=null`.

Create an explicit allow rule for `echo_tool`:

```bash
curl -s -X POST http://127.0.0.1:8891/api/platform/tool-permissions \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  -d '{"agent_id":"agentSmoke","tool_name":"echo_tool"}' \
  | python -m json.tool
```

Invoke `echo_tool` with the existing payload shape:

```bash
curl -s -X POST http://127.0.0.1:8891/api/platform/tools/echo_tool/invoke \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  -d '{"agent_id":"agentSmoke","session_id":"sessionSmoke","arguments":{"hello":"world"}}' \
  | python -m json.tool
```

Expected: response contains `status=success`, `trace_id`, `duration_ms`, and the echoed arguments.

Check default deny still works:

```bash
curl -s -X POST http://127.0.0.1:8891/api/platform/tools/time_tool/invoke \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  -d '{"agent_id":"agentSmoke","session_id":"sessionSmoke","arguments":{}}' \
  | python -m json.tool
```

Expected: `PERMISSION_DENIED` unless an explicit allow rule was added for `time_tool`.

Check timeout still works:

```bash
curl -s -X POST http://127.0.0.1:8891/api/platform/tool-permissions \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  -d '{"agent_id":"agentSmoke","tool_name":"slow_tool"}' \
  | python -m json.tool

curl -s -X POST http://127.0.0.1:8891/api/platform/tools/slow_tool/invoke \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  -d '{"agent_id":"agentSmoke","session_id":"sessionSmoke","arguments":{"sleep_seconds":2},"timeout_seconds":0.1}' \
  | python -m json.tool
```

Expected: `TOOL_TIMEOUT` and an audit/tracing record.

Check audit records:

```bash
curl -s \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  "http://127.0.0.1:8891/api/platform/audit/tool-calls?agent_id=agentSmoke&session_id=sessionSmoke" \
  | python -m json.tool
```

Expected: allowed, denied, and timeout attempts have `trace_id`, `status`, `duration_ms`, and `error_code`.

Phase 1.5 AgentScope facade smoke tests are still documented in [phase1_5-platform-api.md](phase1_5-platform-api.md). Session, chat, and message verification should continue to use those commands.

## Local Syntax Check

```bash
python -m compileall backend/app
```

On Windows, if existing `__pycache__` permissions block direct compilation, use the active project environment:

```powershell
conda run -n agent-platform python -m compileall backend\app
```

## ECS Smoke Test

After local commit and push:

```bash
cd /app/agent-platform
git pull
source .venv/bin/activate
uvicorn backend.app.main:app --host 0.0.0.0 --port 8891
```

Then run the same curl commands against:

```text
http://127.0.0.1:8891
```

or the ECS intranet/public IP as appropriate.

## Next Step

Phase 2.3.2 should design and implement the `extra_agent_tools` adapter. That adapter should convert selected platform registry entries into AgentScope-native tools only after verifying the exact AgentScope 2.0.3 `ToolBase` or `FunctionTool` signatures in the installed environment.


## ECS Smoke Test Result

Date: 2026-07-01
Port: 8891
Result: Passed

Verified:
- /api/platform/overview returns phase-2.3.1.
- /api/platform/overview includes tool_native_metadata=true.
- /api/platform/tools returns native metadata fields:
  - tool_name
  - description
  - native_type
  - native_ref
  - timeout_seconds
  - enabled
- echo_tool, time_tool, and slow_tool are registered as native_type=mock.
- native_ref is null for current mock tools.
- Backward-compatible fields name, input_schema, and default_timeout_seconds are still returned.
- /api/platform/tools/{tool_name}/invoke remains compatible with the existing request body.
- echo_tool invocation still works.
- Permission, audit, and tracing behavior remains functional.

Conclusion:
Phase 2.3.1 tool native metadata passed ECS smoke test.
# Phase 2 Workspace + Tool + Permission

Phase 2 adds enterprise platform primitives on top of the existing AgentScope Agent Service integration.

This phase does not implement RAG, Long-term Memory, Agent Team, or frontend UI. AgentScope native APIs remain available.

## Goals

- Resolve and create isolated workspace directories.
- Register safe mock tools.
- Enforce default deny tool permission.
- Allow explicit tool permission via JSON config.
- Record each tool call to local JSONL audit log.

## Workspace Isolation

Workspace paths are generated as:

```text
WORKSPACE_BASEDIR/tenant_id/user_id/agent_id/session_id
```

The platform never accepts tenant_id or user_id from query parameters. They are read from:

```text
X-Tenant-ID
X-User-ID
```

This prevents a caller from resolving another tenant's workspace path.

## Tool Registry

Phase 2 includes only safe mock tools:

- `echo_tool`: returns the input JSON arguments.
- `time_tool`: returns current UTC time.

No shell command execution is implemented. No real enterprise system is connected.

## Permission Model

Tool invocation is default deny.

Set `PLATFORM_TOOL_PERMISSION_FILE` to a JSON file with explicit allow rules:

```json
{
  "allow": [
    {
      "tenant_id": "tenantA",
      "user_id": "userA",
      "agent_id": "*",
      "tool_name": "echo_tool"
    }
  ]
}
```

Supported wildcard: `*`.

Permission dimensions:

- `tenant_id`
- `user_id`
- `agent_id`
- `tool_name`

## Audit Log

Every tool invocation writes one JSONL record:

```json
{
  "tenant_id": "tenantA",
  "user_id": "userA",
  "agent_id": "agent_demo",
  "session_id": "session_demo",
  "tool_name": "echo_tool",
  "allowed": true,
  "timestamp": "2026-07-01T00:00:00+00:00"
}
```

Default file:

```text
logs/tool-calls-audit.jsonl
```

Override with:

```text
PLATFORM_TOOL_AUDIT_LOG_FILE=logs/tool-calls-audit.jsonl
```

## New APIs

- `GET /api/platform/workspaces/resolve?agent_id=...&session_id=...&create=true`
- `GET /api/platform/tools`
- `POST /api/platform/tools/{tool_name}/invoke`
- `GET /api/platform/audit/tool-calls`

## Local Smoke Test

The commands below are intended for local Windows VS Code development or ECS shell after `git pull`.

### 1. Configure Local Permission File

Create a local permission config from the committed example:

```bash
mkdir -p config logs
cp deploy/examples/tool-permissions.example.json config/tool-permissions.local.json
```

Add these values to your local `.env` before starting the backend:

```bash
PLATFORM_TOOL_PERMISSION_FILE=config/tool-permissions.local.json
PLATFORM_TOOL_AUDIT_LOG_FILE=logs/tool-calls-audit.jsonl
```

For local-only workspace testing, you may also use:

```bash
WORKSPACE_BASEDIR=.runtime/workspaces
```

Do not commit your real `.env`.

### 2. Start Backend

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8891
```

### 3. Health

```bash
curl -s http://127.0.0.1:8891/platform/health | python -m json.tool
```

### 4. Overview

```bash
curl -s \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  http://127.0.0.1:8891/api/platform/overview \
  | python -m json.tool
```

Expected feature flags include:

- `workspace: true`
- `tools: true`
- `permission: true`
- `tool_audit: true`

### 5. Resolve Workspace

```bash
export AGENT_ID="agent_demo"
export SESSION_ID="session_demo"

curl -s \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  "http://127.0.0.1:8891/api/platform/workspaces/resolve?agent_id=${AGENT_ID}&session_id=${SESSION_ID}&create=true" \
  | python -m json.tool
```

Expected path contains:

```text
tenantA/userA/agent_demo/session_demo
```

### 6. List Tools

```bash
curl -s \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  http://127.0.0.1:8891/api/platform/tools \
  | python -m json.tool
```

Expected tools:

- `echo_tool`
- `time_tool`

### 7. Invoke Allowed Tool

The example permission file allows `tenantA/userA` to call both mock tools for any agent.

```bash
python - <<'PY'
import json
body = {
    "agent_id": "agent_demo",
    "session_id": "session_demo",
    "arguments": {
        "message": "hello phase 2"
    }
}
open("/tmp/platform_tool_echo.json", "w", encoding="utf-8").write(json.dumps(body, ensure_ascii=False))
PY

curl -s -X POST "http://127.0.0.1:8891/api/platform/tools/echo_tool/invoke" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  --data-binary "@/tmp/platform_tool_echo.json" \
  | python -m json.tool
```

Expected:

```json
{
  "tool_name": "echo_tool",
  "allowed": true
}
```

### 8. Invoke Denied Tool From Another Tenant

```bash
curl -s -X POST "http://127.0.0.1:8891/api/platform/tools/echo_tool/invoke" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: tenantB" \
  -H "X-User-ID: userA" \
  --data-binary "@/tmp/platform_tool_echo.json" \
  | python -m json.tool
```

Expected HTTP status is `403`. This verifies default deny and tenant-level isolation.

### 9. Invoke Time Tool

```bash
python - <<'PY'
import json
body = {
    "agent_id": "agent_demo",
    "session_id": "session_demo",
    "arguments": {}
}
open("/tmp/platform_tool_time.json", "w", encoding="utf-8").write(json.dumps(body, ensure_ascii=False))
PY

curl -s -X POST "http://127.0.0.1:8891/api/platform/tools/time_tool/invoke" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  --data-binary "@/tmp/platform_tool_time.json" \
  | python -m json.tool
```

### 10. Read Audit Log

```bash
curl -s \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  "http://127.0.0.1:8891/api/platform/audit/tool-calls?agent_id=agent_demo&session_id=session_demo" \
  | python -m json.tool
```

Then verify tenantB cannot read tenantA's allowed audit records. Because the denied tenantB invocation above is also audited, tenantB may see its own denied records, but it must not see tenantA's allowed records.

```bash
curl -s \
  -H "X-Tenant-ID: tenantB" \
  -H "X-User-ID: userA" \
  "http://127.0.0.1:8891/api/platform/audit/tool-calls?agent_id=agent_demo&session_id=session_demo" \
  | python -m json.tool
```

Expected: `tenantB/userA` does not see `tenantA/userA` audit records.

## Known Limits

- Permission config is local JSON, loaded at runtime.
- Changing permission config may require backend restart depending on deployment process.
- Audit log is local JSONL, not a database.
- Workspace API only creates directories and returns paths. It does not manage files.
- Tools are mock-only.
- No RAG, Memory, Team, frontend, or real enterprise tool integration in this phase.

## Phase 3+ Direction

Phase 3 can add RAG Service. Before that, Phase 2 should be hardened with:

- Tool permission admin API or managed config source.
- Audit retention and rotation.
- Workspace file listing and cleanup policies.
- Tool call tracing middleware.


## ECS Smoke Test Result

Date: 2026-07-01
Port: 8891
Result: Passed

Verified:
- /api/platform/tools returns echo_tool and time_tool.
- /api/platform/workspaces/resolve returns isolated workspace path.
- Workspace path includes tenant_id/user_id/agent_id/session_id isolation.
- Allowed tool call succeeds when explicitly configured in PLATFORM_TOOL_PERMISSION_FILE.
- Denied tool call is blocked by default-deny policy.
- Both allowed and denied tool calls are written to JSONL audit log.
- /api/platform/audit/tool-calls can query audit records.
- Audit query is scoped by X-Tenant-ID and X-User-ID.
- tenantA cannot see tenantB audit records.
- tenantB cannot see tenantA audit records.
- Phase 1.5 chat/session/message APIs still work after Phase 2 changes.

Conclusion:
Phase 2 Workspace + Tool + Permission + Audit passed ECS smoke test.
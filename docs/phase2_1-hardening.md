# Phase 2.1 Hardening

Phase 2.1 strengthens the Phase 2 Workspace + Tool + Permission foundation.

This is still local project development. Do not edit ECS files directly. Deploy by committing locally, pushing to GitHub, then running `git pull` on ECS.

## Scope

Implemented:

- Tool Permission Admin API
- Workspace file listing
- Workspace cleanup preview and safe cleanup
- Tool invocation timeout
- Structured tracing in audit JSONL

Not implemented:

- RAG
- Long-term Memory
- Agent Team
- Frontend
- External tracing systems such as OpenTelemetry or Jaeger
- New database
- Dangerous tools such as shell execution or file deletion tools

## Configuration

Local `.env` should include:

```bash
PLATFORM_TOOL_PERMISSION_FILE=config/tool-permissions.local.json
PLATFORM_TOOL_AUDIT_LOG_FILE=logs/tool-calls-audit.jsonl
PLATFORM_TOOL_TRACE_LOG_FILE=logs/tool-calls-trace.jsonl
WORKSPACE_BASEDIR=.runtime/workspaces
```

Do not commit real `.env`.

## New APIs

- `GET /api/platform/tool-permissions`
- `POST /api/platform/tool-permissions`
- `DELETE /api/platform/tool-permissions/{rule_id}`
- `GET /api/platform/workspaces/files?agent_id=...&session_id=...`
- `POST /api/platform/workspaces/cleanup-preview`
- `POST /api/platform/workspaces/cleanup`

Existing Phase 1.5 and Phase 2 APIs remain compatible.

## Tool Permission Admin

Permission rules are stored in the JSON file pointed to by:

```text
PLATFORM_TOOL_PERMISSION_FILE
```

The admin APIs always use the current request headers:

```text
X-Tenant-ID
X-User-ID
```

Callers cannot set `tenant_id` or `user_id` in body/query to manage another tenant's rules.

## Structured Tracing

Each tool invocation generates a `trace_id`. Audit and trace JSONL records include:

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

Statuses include:

- `success`
- `denied`
- `timeout`
- `not_found`
- `error`

## Local Smoke Test

### 1. Prepare Local Files

```bash
mkdir -p config logs .runtime/workspaces
cp deploy/examples/tool-permissions.example.json config/tool-permissions.local.json
```

Add to local `.env`:

```bash
PLATFORM_TOOL_PERMISSION_FILE=config/tool-permissions.local.json
PLATFORM_TOOL_AUDIT_LOG_FILE=logs/tool-calls-audit.jsonl
PLATFORM_TOOL_TRACE_LOG_FILE=logs/tool-calls-trace.jsonl
WORKSPACE_BASEDIR=.runtime/workspaces
```

### 2. Start Backend

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8891
```

### 3. Health

```bash
curl -s http://127.0.0.1:8891/platform/health | python -m json.tool
```

### 4. List Permission Rules

```bash
curl -s \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  http://127.0.0.1:8891/api/platform/tool-permissions \
  | python -m json.tool
```

### 5. Add Permission Rule

```bash
python - <<'PY'
import json
body = {
    "agent_id": "agent_demo",
    "tool_name": "echo_tool"
}
open("/tmp/tool_permission_body.json", "w", encoding="utf-8").write(json.dumps(body))
PY

curl -s -X POST http://127.0.0.1:8891/api/platform/tool-permissions \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  --data-binary "@/tmp/tool_permission_body.json" \
  | tee /tmp/tool_permission_rule.json | python -m json.tool
```

Extract `RULE_ID`:

```bash
export RULE_ID=$(python - <<'PY'
import json
d = json.load(open("/tmp/tool_permission_rule.json"))
print(d["rule_id"])
PY
)
echo "RULE_ID=$RULE_ID"
```

### 6. Delete Permission Rule

```bash
curl -s -X DELETE \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  "http://127.0.0.1:8891/api/platform/tool-permissions/${RULE_ID}" \
  | python -m json.tool
```

### 7. Resolve Workspace

```bash
export AGENT_ID="agent_demo"
export SESSION_ID="session_demo"

curl -s \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  "http://127.0.0.1:8891/api/platform/workspaces/resolve?agent_id=${AGENT_ID}&session_id=${SESSION_ID}&create=true" \
  | python -m json.tool
```

### 8. Create Test Workspace File

Create a file under the resolved workspace directory. Example for local `.runtime`:

```bash
mkdir -p ".runtime/workspaces/tenantA/userA/${AGENT_ID}/${SESSION_ID}"
echo "hello workspace" > ".runtime/workspaces/tenantA/userA/${AGENT_ID}/${SESSION_ID}/hello.txt"
```

### 9. List Workspace Files

```bash
curl -s \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  "http://127.0.0.1:8891/api/platform/workspaces/files?agent_id=${AGENT_ID}&session_id=${SESSION_ID}" \
  | python -m json.tool
```

Expected: `hello.txt` appears. Another tenant must not see this workspace.

### 10. Cleanup Preview

```bash
python - <<'PY'
import json, os
body = {
    "agent_id": os.environ["AGENT_ID"],
    "session_id": os.environ["SESSION_ID"],
    "max_age_days": 0,
    "dry_run": True
}
open("/tmp/workspace_cleanup.json", "w", encoding="utf-8").write(json.dumps(body))
PY

curl -s -X POST http://127.0.0.1:8891/api/platform/workspaces/cleanup-preview \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  --data-binary "@/tmp/workspace_cleanup.json" \
  | python -m json.tool
```

Expected: candidates are returned and no files are deleted.

### 11. Tool Timeout

`slow_tool` is safe and only sleeps. It can trigger timeout.

```bash
python - <<'PY'
import json
body = {
    "agent_id": "agent_demo",
    "session_id": "session_demo",
    "timeout_seconds": 0.1,
    "arguments": {
        "sleep_seconds": 2
    }
}
open("/tmp/slow_tool_timeout.json", "w", encoding="utf-8").write(json.dumps(body))
PY

curl -s -X POST http://127.0.0.1:8891/api/platform/tools/slow_tool/invoke \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  --data-binary "@/tmp/slow_tool_timeout.json" \
  | python -m json.tool
```

Expected error detail:

```json
{
  "error_code": "TOOL_TIMEOUT"
}
```

### 12. Successful Tool Call With Trace

```bash
python - <<'PY'
import json
body = {
    "agent_id": "agent_demo",
    "session_id": "session_demo",
    "arguments": {
        "message": "trace me"
    }
}
open("/tmp/echo_tool_trace.json", "w", encoding="utf-8").write(json.dumps(body))
PY

curl -s -X POST http://127.0.0.1:8891/api/platform/tools/echo_tool/invoke \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  --data-binary "@/tmp/echo_tool_trace.json" \
  | python -m json.tool
```

Expected response includes:

- `trace_id`
- `status=success`
- `duration_ms`

### 13. Audit Query

```bash
curl -s \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  "http://127.0.0.1:8891/api/platform/audit/tool-calls?agent_id=agent_demo&session_id=session_demo" \
  | python -m json.tool
```

Expected records include allowed, denied, timeout, and success entries with tracing fields.

## ECS Smoke Test

After local commit and push:

```bash
cd /app/agent-platform
git pull
pip install -r backend/requirements.txt
```

Update ECS `.env` manually if needed:

```bash
PLATFORM_TOOL_PERMISSION_FILE=config/tool-permissions.local.json
PLATFORM_TOOL_AUDIT_LOG_FILE=logs/tool-calls-audit.jsonl
PLATFORM_TOOL_TRACE_LOG_FILE=logs/tool-calls-trace.jsonl
```

Then restart uvicorn on port `8891` and run the same smoke test commands against:

```text
http://127.0.0.1:8891
```

## Acceptance Checklist

- [ ] Can list, add, and delete permission rules for current tenant/user.
- [ ] Default deny still works.
- [ ] Explicit allow can invoke tools.
- [ ] Workspace files only show current tenant/user/agent/session files.
- [ ] Cleanup preview does not delete files.
- [ ] Tool timeout returns `TOOL_TIMEOUT`.
- [ ] Allowed, denied, timeout, and not found calls write audit logs.
- [ ] Each tool call has `trace_id`.
- [ ] Audit/tracing includes `duration_ms`, `status`, `error_code`.
- [ ] Phase 1.5 and Phase 2 APIs remain compatible.

## Known Limits

- Permission admin is file-backed JSON, not a database.
- Concurrent writes to the same permission file are not yet locked.
- Cleanup can delete files only when `dry_run=false`; keep default `dry_run=true` for demos.
- Trace logs are JSONL files, not OpenTelemetry.
- Mock tools only. No shell, no system command execution, no real enterprise integrations.



## ECS Smoke Test Result

Date: 2026-07-01
Port: 8891
Result: Passed

Verified:
- /api/platform/tool-permissions can list, create, and delete permission rules.
- Default-deny permission policy works.
- Explicit allow rule enables tool invocation.
- Removing allow rule restores deny behavior.
- /api/platform/workspaces/resolve returns isolated workspace path.
- /api/platform/workspaces/files returns files only from the current workspace.
- cleanup-preview works with dry_run=true and does not delete files.
- slow_tool can trigger TOOL_TIMEOUT.
- allowed, denied, and timeout tool calls are written to audit JSONL.
- New Phase 2.1 audit records include trace_id, status, started_at, finished_at, duration_ms, and error_code.
- audit query supports filtering by tool_name and allowed.
- audit query is scoped by X-Tenant-ID and X-User-ID.
- Phase 1.5 chat/session/message APIs still work.

Conclusion:
Phase 2.1 platform hardening passed ECS smoke test.
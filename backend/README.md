# Backend

This backend is the AgentScope Enterprise Multi-Tenant Agent Platform service entry.

In Phase 1, `backend.app.main:app` is the FastAPI app returned by AgentScope 2.0.3 `create_app`. Platform routes are added with `include_router`, so the AgentScope app is not nested inside another FastAPI app.

The backend initializes:

- `RedisStorage`
- `RedisMessageBus`
- `LocalWorkspaceManager`
- `extra_agent_tools`
- `extra_agent_middlewares`

## Local Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
uvicorn backend.app.main:app --host 0.0.0.0 --port 8891 --reload
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
Copy-Item .env.example .env
uvicorn backend.app.main:app --host 0.0.0.0 --port 8891 --reload
```

Open:

```text
http://127.0.0.1:8891/docs
```

## ECS Start

On Kylin Linux Advanced Server V10:

```bash
git pull
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
bash deploy/scripts/check-env.sh
bash deploy/scripts/start-backend.sh
```

## Test X-User-ID

```bash
curl -H "X-User-ID: userA" -H "X-Tenant-ID: tenantA" http://127.0.0.1:8891/api/me
```

## Platform Health

```bash
curl http://127.0.0.1:8891/platform/health
```

ECS 演示环境统一使用 `8891`，因为 `8000` 已被已有服务占用。本地开发如果 `8000` 没被占用，可以在 `.env` 或启动命令中自行改回 `8000`。

## AgentScope Native APIs

The following APIs are expected to come from AgentScope Agent Service:

- Credential APIs
- Agent template APIs
- Session APIs
- Chat APIs
- `/sessions/{session_id}/stream`
- `/sessions/{session_id}/messages`

Check the generated OpenAPI page at `/docs` for exact paths and request schemas in the installed AgentScope 2.0.3 build.

## Phase 1.5 Platform Facade

Enterprise clients should use platform APIs under `/api/platform/...`:

- `GET /api/platform/overview`
- `POST /api/platform/credentials`
- `GET /api/platform/agents`
- `POST /api/platform/agents`
- `GET /api/platform/sessions?agent_id=...`
- `POST /api/platform/sessions`
- `POST /api/platform/chat`
- `GET /api/platform/sessions/{session_id}/messages?agent_id=...`
- `GET /api/platform/sessions/{session_id}/stream-url?agent_id=...`

The native AgentScope APIs remain available for low-level debugging. The platform facade forwards requests to native endpoints with `X-User-ID` rewritten as `tenant_id:user_id`, for example `tenantA:userA`.

Do not log, return, or commit real API keys. Use `<YOUR_API_KEY>` or environment variables in examples.

Full smoke test: [../docs/phase1_5-platform-api.md](../docs/phase1_5-platform-api.md).

## Phase 2 Workspace, Tool, Permission

Phase 2 adds platform-owned enterprise primitives without changing AgentScope native APIs:

- `GET /api/platform/workspaces/resolve`
- `GET /api/platform/tools`
- `POST /api/platform/tools/{tool_name}/invoke`
- `GET /api/platform/audit/tool-calls`

Workspace paths are resolved by `tenant_id/user_id/agent_id/session_id`. Tool invocation is default deny. Add explicit allow rules with `PLATFORM_TOOL_PERMISSION_FILE`.

Example permission file:

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

Tool audit is written to `PLATFORM_TOOL_AUDIT_LOG_FILE`, defaulting to `logs/tool-calls-audit.jsonl`.

Full smoke test: [../docs/phase2-workspace-tool-permission.md](../docs/phase2-workspace-tool-permission.md).

## Phase 2.1 Hardening

Phase 2.1 adds:

- Tool Permission Admin API
- Workspace file listing
- Workspace cleanup preview and safe cleanup
- Tool invocation timeout
- Structured tracing fields in audit records

New APIs:

- `GET /api/platform/tool-permissions`
- `POST /api/platform/tool-permissions`
- `DELETE /api/platform/tool-permissions/{rule_id}`
- `GET /api/platform/workspaces/files`
- `POST /api/platform/workspaces/cleanup-preview`
- `POST /api/platform/workspaces/cleanup`

Tool calls return or record `trace_id`, `status`, `duration_ms`, and `error_code`. Traces are written to JSONL through `PLATFORM_TOOL_TRACE_LOG_FILE`.

Full smoke test: [../docs/phase2_1-hardening.md](../docs/phase2_1-hardening.md).

## Current TODO

- Smoke test Credential / Agent / Session / Message APIs through official Agent Service.
- Smoke test Chat and SSE event stream.
- Add Redis password / TLS options if the ECS Redis requires them.
- Add DockerWorkspaceManager after local workspace flow is stable.
- Add tenant-aware permission checks and audit middleware.

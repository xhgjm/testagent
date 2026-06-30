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

## Current TODO

- Smoke test Credential / Agent / Session / Message APIs through official Agent Service.
- Smoke test Chat and SSE event stream.
- Add Redis password / TLS options if the ECS Redis requires them.
- Add DockerWorkspaceManager after local workspace flow is stable.
- Add tenant-aware permission checks and audit middleware.

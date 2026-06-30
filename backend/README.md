# Backend

This backend is the MVP scaffold for the AgentScope Enterprise Multi-Tenant Agent Platform.

It is intentionally small in Phase 0. The current code provides a FastAPI entry point, environment loading, MVP header-based identity, platform context, and extension points for AgentScope Agent Service.

## Local Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
Copy-Item .env.example .env
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```

Open:

```text
http://127.0.0.1:8000/docs
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
curl -H "X-User-ID: userA" -H "X-Tenant-ID: tenantA" http://127.0.0.1:8000/api/me
```

## Current TODO

- Confirm AgentScope 2.0.3 Agent Service `create_app` import path.
- Connect RedisStorage and RedisMessageBus.
- Connect LocalWorkspaceManager / DockerWorkspaceManager.
- Add Credential / Agent / Session / Message APIs through official Agent Service.
- Add Chat and SSE event stream.
- Add tenant-aware permission checks and audit middleware.

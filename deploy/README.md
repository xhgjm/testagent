# Deploy

This directory contains deployment notes and examples for running the AgentScope enterprise platform on ECS.

Target environment:

- Kylin Linux Advanced Server V10 (Halberd)
- Python 3.11+
- Redis
- Optional Qdrant
- Existing AgentScope / AgentScope Studio installation

Files:

- `ecs-kylin.md`: ECS deployment plan.
- `scripts/start-backend.sh`: Start backend with uvicorn.
- `scripts/stop-backend.sh`: Stop backend started by the script.
- `scripts/check-env.sh`: Validate Python, pip, git, Redis, `.env`, and important variables.
- `systemd/agent-platform-backend.service.example`: systemd service template.

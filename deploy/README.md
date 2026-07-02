# 部署说明

本目录存放 AgentScope 企业级多租户 Agent 平台在 ECS 上运行所需的部署说明、脚本和示例配置。

目标环境：

- Kylin Linux Advanced Server V10 (Halberd)
- Python 3.11+
- Redis
- 可选 Qdrant
- 已部署 AgentScope / AgentScope Studio

## 文件说明

- `ecs-kylin.md`：Kylin ECS 部署方案。
- `scripts/start-backend.sh`：使用 uvicorn 启动后端。
- `scripts/stop-backend.sh`：停止由启动脚本拉起的后端进程。
- `scripts/check-env.sh`：检查 Python、pip、git、Redis、`.env` 和关键环境变量。
- `systemd/agent-platform-backend.service.example`：systemd 服务模板。

## 端口说明

ECS 演示环境统一使用 `8891`，因为 `8000` 已被已有服务占用。本地开发如果 `8000` 没被占用，可以在 `.env` 或启动命令中自行调整。

## 部署流程摘要

1. 在 ECS 上执行 `git clone` 或 `git pull`。
2. 创建 Python venv 或 conda 环境。
3. 执行 `pip install -r backend/requirements.txt`。
4. 复制 `.env.example` 为 `.env`，填入真实环境变量和 API Key。
5. 执行 `bash deploy/scripts/check-env.sh`。
6. 执行 `bash deploy/scripts/start-backend.sh`。
7. 打开 `http://ECS-IP:8891/docs` 检查接口文档。
8. 后续使用 systemd 接管后端进程。

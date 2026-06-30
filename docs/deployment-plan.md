# Deployment Plan

## Local Development

开发者在本地 VS Code 修改代码，通过 Git 提交同步到 ECS。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
uvicorn backend.app.main:app --host 0.0.0.0 --port 8891 --reload
```

## ECS Runtime

ECS 环境：

- Kylin Linux Advanced Server V10 (Halberd)
- Python 3.11+
- Redis
- 已部署 AgentScope
- 已部署 AgentScope Studio

部署目录建议：

```text
/opt/agent-platform
/data/agent-platform/workspaces
/data/agent-platform/blobs
```

## Release Flow

1. 本地开发并运行基础检查。
2. Git commit。
3. Git push。
4. ECS `git pull`。
5. ECS `pip install -r backend/requirements.txt`。
6. ECS `bash deploy/scripts/check-env.sh`。
7. ECS 重启 backend。
8. 打开 `/docs` 验证。

## Rollback

保持每一步可回滚：

```bash
git log --oneline
git checkout <previous_commit>
bash deploy/scripts/stop-backend.sh
bash deploy/scripts/start-backend.sh
```

生产环境回滚应优先使用 Git tag 或发布制品版本。

## Future Deployment Improvements

- systemd 正式服务文件。
- Docker Compose for backend + Redis + Qdrant。
- Nginx 反向代理和 TLS。
- CI/CD 自动部署。
- 结构化日志、指标和告警。

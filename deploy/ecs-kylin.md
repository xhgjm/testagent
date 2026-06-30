# ECS Kylin Deployment Plan

目标系统：Kylin Linux Advanced Server V10 (Halberd)。

## 1. Python

使用 Python 3.11+。如果系统 Python 版本较低，建议通过 pyenv、conda 或运维标准方式安装独立 Python 环境。

```bash
python --version
pip --version
```

## 2. Redis

Redis 可使用已有服务，也可以由运维安装。

```bash
redis-cli -h 127.0.0.1 -p 6379 ping
```

## 3. Optional Qdrant

RAG Service 阶段可通过 Docker 部署 Qdrant：

```bash
docker run -d --name qdrant -p 6333:6333 -v /data/qdrant:/qdrant/storage qdrant/qdrant
```

第一阶段仅预留 Qdrant 配置，不强制启动。

## 4. Code

```bash
cd /opt
git clone <YOUR_REPO_URL> agent-platform
cd agent-platform
```

后续更新：

```bash
git pull
```

## 5. Python Environment

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
```

## 6. Environment Variables

```bash
cp .env.example .env
vi .env
```

注意：

- 不要提交真实 `.env`。
- API Key、token、密码只写入 ECS 本地 `.env` 或企业密钥系统。
- `WORKSPACE_BASEDIR` 和 `BLOB_STORE_ROOT` 建议放在 `/data/agent-platform/`。

## 7. Start Backend

```bash
bash deploy/scripts/check-env.sh
bash deploy/scripts/start-backend.sh
```

打开：

```text
http://ECS-IP:8000/docs
```

## 8. systemd

复制并修改示例：

```bash
sudo cp deploy/systemd/agent-platform-backend.service.example /etc/systemd/system/agent-platform-backend.service
sudo vi /etc/systemd/system/agent-platform-backend.service
sudo systemctl daemon-reload
sudo systemctl enable agent-platform-backend
sudo systemctl start agent-platform-backend
sudo systemctl status agent-platform-backend
```

## 9. Frontend

第一阶段可以复用 AgentScope Studio 或 examples/web_ui 进行演示。自研企业前端在后续阶段接入 `BACKEND_BASE_URL`。

# 后端服务

本目录是 AgentScope 企业级多租户 Agent 平台的后端入口。

Phase 1 中，`backend.app.main:app` 直接使用 AgentScope 2.0.3 `create_app` 返回的 FastAPI 应用。平台自定义路由通过 `include_router` 挂载到同一个应用上，因此没有把 AgentScope 应用嵌套进另一个 FastAPI 应用。

后端启动时会初始化：

- `RedisStorage`
- `RedisMessageBus`
- `LocalWorkspaceManager`
- `extra_agent_tools`
- `extra_agent_middlewares`

## 本地启动

Linux / macOS：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
uvicorn backend.app.main:app --host 0.0.0.0 --port 8891 --reload
```

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
Copy-Item .env.example .env
uvicorn backend.app.main:app --host 0.0.0.0 --port 8891 --reload
```

启动后打开：

```text
http://127.0.0.1:8891/docs
```

## ECS 启动

在 Kylin Linux Advanced Server V10 上：

```bash
git pull
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
bash deploy/scripts/check-env.sh
bash deploy/scripts/start-backend.sh
```

ECS 演示环境统一使用 `8891` 端口，因为 `8000` 已被已有服务占用。本地开发如果 `8000` 没被占用，可以在 `.env` 或启动命令中自行调整。

## 基础检查

模拟用户：

```bash
curl -H "X-User-ID: userA" -H "X-Tenant-ID: tenantA" http://127.0.0.1:8891/api/me
```

健康检查：

```bash
curl http://127.0.0.1:8891/platform/health
```

## AgentScope 原生接口

以下能力来自 AgentScope Agent Service：

- Credential 接口
- Agent 模板接口
- Session 接口
- Chat 接口
- `/sessions/{session_id}/stream`
- `/sessions/{session_id}/messages`

具体路径和请求结构以当前安装的 AgentScope 2.0.3 在 `/docs` 生成的 OpenAPI 页面为准。

## 平台封装接口

企业侧推荐调用 `/api/platform/...` 下的平台接口。平台层会把 `X-User-ID` 改写为 `tenant_id:user_id` 后转发给原生接口，例如 `tenantA:userA`，以此实现基础租户隔离。

不要在日志、响应或仓库中写入真实 API Key。示例中统一使用 `<YOUR_API_KEY>` 或环境变量。

## Phase 2 Runtime Tool Governance

Phase 2 已完成以下治理能力：

- 平台 Tool Registry 元数据
- 默认拒绝权限模型
- Tool Permission Admin API
- 平台主动工具调用审计和追踪
- 默认关闭的 `extra_agent_tools` adapter
- runtime 执行时二次权限校验
- `runtime_echo_tool` runtime audit/tracing
- runtime workspace context
- WorkspaceManager 对齐设计

Runtime tools 默认关闭：

```env
PLATFORM_ENABLE_RUNTIME_TOOLS=false
PLATFORM_RUNTIME_TOOLS_MODE=disabled
PLATFORM_ENABLE_RUNTIME_AUDIT=false
PLATFORM_RUNTIME_AUDIT_MODE=disabled
```

只有显式开启 mock mode，并且平台 permission JSON 存在 allow 规则时，才会注入安全 mock 工具 `runtime_echo_tool`。该工具不读写文件、不访问网络、不执行系统命令、不接 MCP / Skill / 企业系统。

## 回归脚本

Phase 2.4 runtime governance 回归入口：

```bash
python scripts/smoke_phase2_4_runtime_governance.py
```

该脚本复用 Phase 2.3.7 runtime smoke，使用 `.cache` 下的临时 permission、audit、trace 和 workspace 文件，不依赖真实 `.env`，不启动 server，不访问网络，不连接 MCP / Skill。

## 当前 TODO

- 继续通过官方 Agent Service 冒烟验证 Credential / Agent / Session / Message。
- 继续冒烟验证 Chat 和 SSE 事件流。
- 如果 ECS Redis 需要密码或 TLS，补充 Redis 连接配置。
- 本地 workspace 流程稳定后，再评估 DockerWorkspaceManager。
- runtime tools 和 runtime audit 默认保持关闭。
- 下一步进入 Phase 3 RAG Service 设计，优先做 AgentScope RAG Service 之上的平台 facade。
- 是否需要 custom WorkspaceManager，等 RAG / MCP / Skill 生命周期需求更清楚后再决定。

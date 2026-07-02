# AgentScope 企业级多租户 Agent 平台

本项目基于 AgentScope 2.0.3，目标是建设一个企业级多租户、多用户、多 Agent、多 Session 的 Agent 平台底座。

当前阶段：Phase 2.4 Runtime Tool Governance Closure。Phase 2 的 Workspace、Tool、Permission、Audit、Tracing、runtime tool adapter、runtime permission boundary、runtime audit、runtime workspace alignment 和 WorkspaceManager alignment design 已完成收口。下一阶段建议进入 Phase 3 RAG Service。

本项目不是单体 RAG 问答机器人，也不是只跑 AgentScope 官方 Demo。RAG 是平台能力之一，不是整个平台本身。平台主链路是：

```text
Tenant / User -> Credential -> Agent -> Session -> Chat -> SSE -> Message History -> Workspace -> Tool / Permission / Audit
```

Agent 是模板，Session 是运行状态。所有资源设计都围绕 `tenant_id`、`user_id`、`agent_id`、`session_id` 的隔离边界展开。

## 项目定位

- 项目名称：AgentScope Enterprise Multi-Tenant Agent Platform
- 技术基座：AgentScope 2.0.3 Agent Service
- 运行环境：Kylin Linux Advanced Server V10 (Halberd) ECS
- 开发方式：本地 VS Code 开发，通过 Git 同步到 ECS 部署
- 身份方式：第一阶段使用 `X-Tenant-ID` / `X-User-ID` 模拟身份，后续替换为 JWT / OAuth / 企业统一登录
- 暂不接入：HiMarket，后续作为 API Gateway / 应用市场方向接入

## 已完成能力

### Phase 1：Agent Service 主链路

后端入口已接入 AgentScope 2.0.3 `create_app`，初始化：

- `RedisStorage`
- `RedisMessageBus`
- `LocalWorkspaceManager`
- `extra_agent_tools`
- `extra_agent_middlewares`

AgentScope 原生接口继续保留，用于底层调试。

### Phase 1.5：平台 API facade

企业侧推荐调用 `/api/platform/...`：

- `GET /api/platform/overview`
- `POST /api/platform/credentials`
- `GET /api/platform/agents`
- `POST /api/platform/agents`
- `GET /api/platform/sessions?agent_id=...`
- `POST /api/platform/sessions`
- `POST /api/platform/chat`
- `GET /api/platform/sessions/{session_id}/messages?agent_id=...`
- `GET /api/platform/sessions/{session_id}/stream-url?agent_id=...`

平台层通过 `scoped_user_id = tenant_id:user_id` 调用 AgentScope 原生接口，实现基础租户隔离。例如外部请求 `X-Tenant-ID: tenantA`、`X-User-ID: userA`，内部转发给 AgentScope 时使用 `X-User-ID: tenantA:userA`。

### Phase 2：Workspace / Tool / Permission / Audit

平台新增：

- `GET /api/platform/workspaces/resolve`
- `GET /api/platform/tools`
- `POST /api/platform/tools/{tool_name}/invoke`
- `GET /api/platform/audit/tool-calls`

Workspace 路径按 `tenant_id/user_id/agent_id/session_id` 生成。工具调用默认拒绝，只有显式 allow 规则才能调用。工具审计写入 JSONL。

### Phase 2.1：治理加固

新增：

- Tool Permission Admin API
- Workspace 文件列表
- Workspace 清理预览和安全清理
- 工具调用超时
- 结构化 tracing 字段

新增接口：

- `GET /api/platform/tool-permissions`
- `POST /api/platform/tool-permissions`
- `DELETE /api/platform/tool-permissions/{rule_id}`
- `GET /api/platform/workspaces/files`
- `POST /api/platform/workspaces/cleanup-preview`
- `POST /api/platform/workspaces/cleanup`

### Phase 2.3：Runtime Tool Governance

Phase 2.3 完成了 runtime tool 治理链路：

- Tool Registry 增加 `native_type` / `native_ref` / `enabled` / `timeout_seconds`
- 核验 AgentScope `extra_agent_tools` / `extra_agent_middlewares` 签名
- 实现默认关闭的 `extra_agent_tools` adapter skeleton
- 实现 runtime 执行时二次权限边界
- 实现 runtime audit / tracing
- 实现 runtime workspace context
- 完成 WorkspaceManager alignment design
- 增加本地 runtime 回归脚本

Runtime tools 默认关闭：

```env
PLATFORM_ENABLE_RUNTIME_TOOLS=false
PLATFORM_RUNTIME_TOOLS_MODE=disabled
PLATFORM_ENABLE_RUNTIME_AUDIT=false
PLATFORM_RUNTIME_AUDIT_MODE=disabled
```

只有显式开启 mock mode，并且平台 permission JSON 存在 allow 规则时，才会注入安全 mock 工具 `runtime_echo_tool`。该工具不读写文件、不访问网络、不执行系统命令、不接 MCP / Skill / 企业系统。

### Phase 2.4：Runtime Tool Governance 收口

Phase 2.4 统一了 Phase 2 runtime governance 文档和冒烟测试入口。完整说明见 [docs/phase2_4-runtime-tool-governance-closure.md](docs/phase2_4-runtime-tool-governance-closure.md)。

本地回归入口：

```bash
python scripts/smoke_phase2_4_runtime_governance.py
```

该脚本复用 Phase 2.3.7 runtime smoke，使用临时 permission/audit/workspace 文件，不依赖真实 `.env`，不启动 server，不访问网络。

## 为什么不是单体 RAG

RAG 是企业 Agent 平台的一类能力，不是平台本身。本项目的核心对象包括：

- Tenant：企业租户，资源隔离顶层边界
- User：租户内用户
- Credential：模型或外部系统凭证
- Agent：Agent 模板
- Session：Agent 运行状态
- Message：历史消息
- Event：运行事件和 SSE
- Workspace：运行空间
- Tool：工具能力挂载点
- Permission：权限策略
- Model：模型配置
- RAG KnowledgeBase：后续知识库能力
- Long-term Memory：后续长期记忆能力
- Agent Team：后续多智能体协作能力

平台先建设多租户 Agent 底座，再逐步接入 RAG、Memory、Team 等能力。

## 本地开发

1. 创建虚拟环境：

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

   Windows PowerShell：

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. 安装依赖：

   ```bash
   pip install -r backend/requirements.txt
   ```

3. 准备环境变量：

   ```bash
   cp .env.example .env
   ```

4. 启动后端：

   ```bash
   uvicorn backend.app.main:app --host 0.0.0.0 --port 8891 --reload
   ```

5. 打开接口文档：

   ```text
   http://127.0.0.1:8891/docs
   ```

6. 检查模拟身份：

   ```bash
   curl -H "X-User-ID: userA" -H "X-Tenant-ID: tenantA" http://127.0.0.1:8891/api/me
   ```

7. 检查健康状态：

   ```bash
   curl http://127.0.0.1:8891/platform/health
   ```

ECS 演示环境统一使用 `8891`，因为 `8000` 已被已有服务占用。本地开发如果 `8000` 没被占用，可以在 `.env` 或启动命令中自行调整。

## ECS 部署

目标环境：

- Kylin Linux Advanced Server V10 (Halberd)
- Python 3.11+
- Redis
- 可选 Qdrant
- 已部署 AgentScope / AgentScope Studio

基本流程：

1. 在 ECS 上执行 `git clone` 或 `git pull`。
2. 创建 Python venv 或 conda 环境。
3. 执行 `pip install -r backend/requirements.txt`。
4. 复制 `.env.example` 为 `.env`，填入真实环境变量和 API Key。
5. 执行 `bash deploy/scripts/check-env.sh` 检查环境。
6. 执行 `bash deploy/scripts/start-backend.sh` 启动后端。
7. 打开 `http://ECS-IP:8891/docs` 做演示。
8. 后续用 systemd 接管进程。

更多细节见 [deploy/ecs-kylin.md](deploy/ecs-kylin.md)。

## 验收清单

- [x] 项目结构独立于官方 AgentScope 源码目录。
- [x] 后端可作为 FastAPI 应用启动。
- [x] `/docs` 可打开。
- [x] 支持 `X-User-ID` / `X-Tenant-ID` 模拟身份。
- [x] 接入 AgentScope 2.0.3 `create_app`。
- [x] 初始化 `RedisStorage`、`RedisMessageBus`、`LocalWorkspaceManager`。
- [x] 完成平台 API facade。
- [x] 完成 Workspace / Tool / Permission / Audit 雏形。
- [x] 完成 runtime tool governance 收口。
- [ ] Phase 3 接入 RAG Service。
- [ ] Phase 4 接入 Long-term Memory。
- [ ] Phase 5 接入 Agent Team。

## 路线图

- Phase 0：环境和项目骨架。
- Phase 1：Agent Service 主链路。
- Phase 1.5：平台 API facade 和基础多租户隔离。
- Phase 2：Workspace + Tool + Permission + Audit。
- Phase 2.1：Permission Admin、Workspace 文件和清理、工具超时、结构化 tracing。
- Phase 2.2：AgentScope Native Alignment 设计。
- Phase 2.3：Runtime Tool Governance。
- Phase 2.4：Runtime Tool Governance 收口。
- Phase 3：RAG Service。
- Phase 4：Long-term Memory。
- Phase 5：Agent Team。
- Phase 6：企业鉴权、审计、预算、限流、部署治理。
- Phase 7：HiMarket / API Gateway / 应用市场接入。

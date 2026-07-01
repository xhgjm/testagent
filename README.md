# AgentScope Enterprise Multi-Tenant Agent Platform

基于 AgentScope 2.0.3 的企业级多租户 Agent 平台底座。

当前阶段：Phase 1 / Agent Service integration。

本项目不是单体 RAG 问答机器人，也不是只跑 AgentScope 官方 Demo。它的目标是在 AgentScope 2.0.3 Agent Service 能力之上，沉淀一个可部署、可演示、可扩展的企业 Agent 平台原型，优先跑通企业平台主链路：

User / Tenant -> Credential -> Agent -> Session -> Chat -> SSE Event Stream -> Message History -> Workspace。

Agent Service 已作为后端主入口接入。RAG Service、Long-term Memory、Agent Team、Tool、Permission、Middleware 等能力在第一阶段继续做清晰预留，后续逐步接入。

Phase 1.5 新增平台 API facade。企业入口推荐使用 `/api/platform/...`，AgentScope 原生接口继续保留用于底层调试。

Phase 2 新增 Workspace + Tool + Permission 雏形：平台可以解析并创建租户隔离 workspace，列出 mock tools，按默认 deny / 显式 allow 策略调用工具，并记录工具调用审计。

## Project Positioning

- 平台名称：AgentScope Enterprise Multi-Tenant Agent Platform
- 技术基座：AgentScope 2.0.3 Agent Service
- 运行环境：Kylin Linux Advanced Server V10 (Halberd) ECS
- 开发方式：本地 VS Code 开发，通过 Git 同步到 ECS 部署
- 当前边界：先用 `X-User-ID` / `X-Tenant-ID` 模拟用户和租户身份，后续替换为 JWT / OAuth / 企业统一登录
- 暂不接入：HiMarket。后续作为 API Gateway / 应用市场方向接入

## Phase 1.5 Platform API

企业用户推荐调用平台封装接口：

- `GET /api/platform/overview`
- `POST /api/platform/credentials`
- `GET /api/platform/agents`
- `POST /api/platform/agents`
- `GET /api/platform/sessions?agent_id=...`
- `POST /api/platform/sessions`
- `POST /api/platform/chat`
- `GET /api/platform/sessions/{session_id}/messages?agent_id=...`
- `GET /api/platform/sessions/{session_id}/stream-url?agent_id=...`

AgentScope 原生接口仍保留，用于底层调试。平台层通过 `scoped_user_id = tenant_id:user_id` 调用原生接口，实现基础租户隔离。例如外部请求 `X-Tenant-ID: tenantA`、`X-User-ID: userA`，内部转发给 AgentScope 时使用 `X-User-ID: tenantA:userA`。

不要在请求示例、日志或代码中写入真实 API Key。文档只使用 `<YOUR_API_KEY>` 或环境变量占位。完整 smoke test 见 [docs/phase1_5-platform-api.md](docs/phase1_5-platform-api.md)。

## Phase 2 Workspace + Tool + Permission

新增平台接口：

- `GET /api/platform/workspaces/resolve`
- `GET /api/platform/tools`
- `POST /api/platform/tools/{tool_name}/invoke`
- `GET /api/platform/audit/tool-calls`

Phase 2 只实现企业能力雏形：

- Workspace：按 `tenant_id/user_id/agent_id/session_id` 生成隔离路径，并可创建目录。
- Tool Registry：内置安全 mock tools：`echo_tool`、`time_tool`。
- Permission：工具调用默认 deny，只有 JSON allow-list 显式允许才可调用。
- Audit Log：每次工具调用记录 JSONL 审计日志，包含 tenant、user、agent、session、tool、allowed/denied、timestamp。

完整 smoke test 见 [docs/phase2-workspace-tool-permission.md](docs/phase2-workspace-tool-permission.md)。

## Why Not A Single RAG Bot

RAG 是企业 Agent 平台的一类能力，不是整个平台本身。本项目的核心对象和隔离边界围绕多租户、多用户、多 Agent、多 Session 展开：

- Agent 是模板，描述能力、模型、工具、权限和治理策略。
- Session 是运行状态，承载一次具体用户会话、消息、事件、Workspace 和执行上下文。
- RAG KnowledgeBase 是可被 Agent 或 Tool 挂载的知识资源。
- Long-term Memory 是可按 Agent / User / Tenant 策略开启的长期记忆能力。
- Agent Team 是基于 Leader Session 派生 Worker Session 的多智能体协作能力。

因此，本项目优先建设平台底座，而不是把所有能力折叠成一个 RAG Chat API。

## Core Objects

- Tenant：企业租户，是资源、凭证、知识库、审计和策略的顶层隔离边界。
- User：租户内用户，第一阶段通过 `X-User-ID` 模拟。
- Credential：模型或外部系统凭证，必须按 tenant / user 隔离，不能写入代码。
- Agent：Agent 模板，定义模型、工具、权限、中间件、RAG、Memory、Team 等配置。
- Session：Agent 的一次运行状态，包含会话上下文、消息、事件和 Workspace。
- Message：用户、Agent、Tool、系统之间的历史消息。
- Event：运行时事件，后续通过 SSE / MessageBus 推送。
- Workspace：运行空间，开发阶段可用本地目录，企业阶段可切换 Docker / E2B。
- Tool：企业系统能力挂载点，例如 CRM、工单、数据库只读查询、RAG 检索。
- Permission：工具、数据、Workspace、模型调用等权限控制。
- Model：模型供应商和模型配置，例如 DashScope、DeepSeek、OpenAI compatible。
- RAG KnowledgeBase：多租户知识库服务，后续接 Qdrant、BlobStore、Parser、Chunker、Index worker。
- Long-term Memory：长期记忆能力，默认关闭，需显式策略控制。
- Agent Team：Leader / Worker 多智能体协作能力，后续注册 explorer / coder / tester / reviewer 等 worker。

## Local Development

1. 创建虚拟环境：

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

   Windows PowerShell:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. 安装后端依赖：

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

5. 打开 API 文档：

   ```text
   http://127.0.0.1:8891/docs
   ```

6. 测试模拟用户：

   ```bash
   curl -H "X-User-ID: userA" -H "X-Tenant-ID: tenantA" http://127.0.0.1:8891/api/me
   ```

7. 测试平台健康检查：

   ```bash
   curl http://127.0.0.1:8891/platform/health
   ```

   ECS 演示环境统一使用 `8891`，因为 `8000` 已被已有服务占用。本地开发如果 `8000` 没被占用，可以在 `.env` 或启动命令中自行改回 `8000`。

## ECS Deployment

部署目标环境：

- Kylin Linux Advanced Server V10 (Halberd)
- Python 3.11+
- Redis
- 可选 Qdrant Docker 服务
- AgentScope / AgentScope Studio 已部署

基本流程：

1. 在 ECS 上 `git clone` 或 `git pull` 本项目。
2. 创建 Python venv 或 conda 环境。
3. 执行 `pip install -r backend/requirements.txt`。
4. 复制 `.env.example` 为 `.env`，填入真实环境变量和 API Key。
5. 执行 `bash deploy/scripts/check-env.sh` 检查环境。
6. 执行 `bash deploy/scripts/start-backend.sh` 启动后端。
7. 打开 `http://ECS-IP:8891/docs` 做汇报演示。
8. 后续用 systemd 接管进程。

更多细节见 [deploy/ecs-kylin.md](deploy/ecs-kylin.md)。

## MVP Acceptance Checklist

- [x] 项目结构清晰，独立于官方 AgentScope 源码目录。
- [x] 后端可作为 FastAPI 应用启动。
- [x] `/docs` 可打开。
- [x] 支持 `X-User-ID` / `X-Tenant-ID` 模拟身份。
- [x] Workspace、Tool、Permission、Middleware、RAG、Memory、Team 有明确接入点。
- [x] 接入 AgentScope 2.0.3 Agent Service 的真实入口 `create_app`。
- [x] 初始化 `RedisStorage`、`RedisMessageBus`、`LocalWorkspaceManager`。
- [ ] Credential 创建和隔离验证。TODO: 使用 AgentScope 原生 API 做 smoke test。
- [ ] Agent 模板创建和隔离验证。TODO: 使用 AgentScope 原生 API 做 smoke test。
- [ ] Session 创建和 Chat 主链路。TODO: 使用 AgentScope 原生 API 做 smoke test。
- [ ] SSE Event Stream。TODO: 验证 `/sessions/{session_id}/stream`。
- [ ] Message History 查询。TODO: 验证 `/sessions/{session_id}/messages`。
- [ ] userA / userB 数据隔离验证。
- [ ] Workspace 运行目录隔离验证。

## Roadmap

- Phase 0：环境和项目骨架。
- Phase 1：Agent Service 主链路，接入 `create_app`，打通 User / Credential / Agent / Session / Chat / SSE / Message。
- Phase 1.5：平台 API facade，基于 `tenant_id:user_id` 实现基础租户隔离。
- Phase 2：Workspace + Tool + Permission，增加隔离 workspace、mock tools、默认 deny 权限和工具审计。
- Phase 3：RAG Service，接入 KnowledgeBase、Document、Qdrant、BlobStore、Index worker。
- Phase 4：Long-term Memory，按 Agent 策略启用长期记忆和敏感信息保护。
- Phase 5：Agent Team，支持 Leader Session 派生 Worker Session。
- Phase 6：企业鉴权、审计、预算、限流、部署治理。
- Phase 7：HiMarket / API Gateway / 应用市场接入。

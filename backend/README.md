# 后端服务

本目录是 AgentScope 企业级多租户 Agent 平台的后端入口。

Phase 1 中，`backend.app.main:app` 直接使用 AgentScope 2.0.3 `create_app` 返回的 FastAPI 应用。平台自定义路由通过 `include_router` 挂载到同一个应用上，因此没有把 AgentScope 应用嵌套进另一个 FastAPI 应用。

后端启动时会初始化：

- `RedisStorage`
- `RedisMessageBus`
- `LocalWorkspaceManager`
- `extra_agent_tools`
- `extra_agent_middlewares`

当前阶段：Phase 3.1 RAG Config Skeleton。后端已完成 AgentScope RAG 相关签名核验、平台 RAG facade 设计、RAG 配置骨架和安全状态展示，但尚未启用真实 RAG、Qdrant、embedding、BlobStore、index worker 或 chat RAG。

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

## Phase 3 RAG Service 规划

Phase 3 将在 AgentScope RAG Service 之上增加平台 RAG facade，而不是把平台改造成单体 RAG 问答机器人。

当前已核验的 AgentScope 2.0.3 RAG 能力：

- `create_app` 支持 `knowledge_base_manager`、`knowledge_parsers`、`knowledge_chunker`、`blob_store`、`enable_index_worker`
- `agentscope.rag.KnowledgeBase`
- `ParserBase` / `TextParser` / `PDFParser` / `PPTParser` / `ImageParser`
- `ChunkerBase` / `ApproxTokenChunker`
- `VectorStoreBase` / `QdrantStore`
- `CollectionPerKbManager`
- `LocalBlobStore` / `S3BlobStore`
- `RAGMiddleware`
- 原生 `/knowledge_bases` router

当前 `backend/app/rag` 只是预留目录：

- `config.py` 返回 `RagConfigStatus(effective_enabled=False, runtime_registered=False, ...)`，并解析 Phase 3.1 RAG 配置状态
- `README.md` 说明后续模块规划

Phase 3.1 新增配置：

```env
PLATFORM_ENABLE_RAG=false
PLATFORM_RAG_MODE=disabled
PLATFORM_RAG_NATIVE_BASE_URL=
PLATFORM_RAG_ISOLATION_STRATEGY=collection_per_kb
PLATFORM_RAG_ENABLE_INDEX_WORKER=false
```

`RagConfigStatus.effective_enabled` 表示真实 RAG runtime 是否已经接线。Phase 3.1 中它始终为 `false`，`runtime_registered` 也始终为 `false`，即使 `PLATFORM_ENABLE_RAG=true`。`/api/platform/overview` 会展示 `features.rag` 和扁平 RAG 字段，但不会返回 `PLATFORM_RAG_NATIVE_BASE_URL` 原文。

Phase 3.1 明确拒绝 `PLATFORM_RAG_ENABLE_INDEX_WORKER=true`，状态为 `misconfigured`，并保持 `effective_enabled=false`、`runtime_registered=false`。

`backend/app/main.py` 显式传入禁用状态的 RAG 参数：

```python
knowledge_base_manager=None
knowledge_parsers=None
knowledge_chunker=None
blob_store=None
enable_index_worker=False
```

这些参数不绑定 `PLATFORM_RAG_ENABLE_INDEX_WORKER`。当前没有向 `create_app` 注入真实 RAG 组件。AgentScope 原生 `/knowledge_bases` router 可能存在，但在没有 `knowledge_base_manager` 时预期返回 `503 Service Unavailable`。Phase 3.1 不注册 `/api/platform/knowledge-bases`。

后续 Phase 3.1+ 建议新增：

- `backend/app/rag/schemas.py`
- `backend/app/rag/registry.py`
- `backend/app/rag/native_client.py`
- `backend/app/rag/routes.py`
- `backend/app/rag/permissions.py`
- `backend/app/rag/audit.py`
- `backend/app/rag/bindings.py`

Phase 3.0 没有新增 RAG 外部 API。未来企业入口建议放在：

```text
/api/platform/knowledge-bases
/api/platform/knowledge-bases/{kb_id}/documents
/api/platform/knowledge-bases/{kb_id}/search
/api/platform/agents/{agent_id}/knowledge-bases
```

原生 `/knowledge_bases` 保留给底层调试，企业侧仍应优先使用 `/api/platform/...` facade。

## smoke test 脚本

Phase 2.4 runtime governance smoke test 入口：

```bash
python scripts/smoke_phase2_4_runtime_governance.py
```

该脚本复用 Phase 2.3.7 runtime smoke，使用 `.cache` 下的临时 permission、audit、trace 和 workspace 文件，不依赖真实 `.env`，不启动 server，不访问网络，不连接 MCP / Skill。

Phase 3.1 RAG config skeleton smoke test：

```bash
python scripts/smoke_phase3_1_rag_config.py
```

该脚本不启动 server，不访问网络，不读写真实 `.env`，只验证 RAG 配置状态解析和 fail closed 行为。

## 当前 TODO

- 继续通过官方 Agent Service 执行 Credential / Agent / Session / Message smoke test。
- 继续执行 Chat 和 SSE 事件流 smoke test。
- 如果 ECS Redis 需要密码或 TLS，补充 Redis 连接配置。
- 本地 workspace 流程稳定后，再评估 DockerWorkspaceManager。
- runtime tools 和 runtime audit 默认保持关闭。
- 下一步进入 Phase 3.2 KnowledgeBase facade skeleton，继续默认关闭真实 RAG runtime。
- RAG facade、KB metadata、Document metadata、Agent-KB binding、RAG permission、RAG audit 仍未实现。
- 当前不部署 Qdrant，不接 embedding，不接 BlobStore，不启用 index worker。
- 是否需要 custom WorkspaceManager，等 RAG / MCP / Skill 生命周期需求更清楚后再决定。

# AgentScope 企业级多租户 Agent 平台

本项目基于 AgentScope 2.0.3，目标是建设一个企业级多租户、多用户、多 Agent、多 Session 的 Agent 平台底座。

当前阶段：Phase 3.4 Document File Upload, Parsing and Chunking Skeleton。Phase 2 的 Workspace、Tool、Permission、Audit、Tracing、runtime tool adapter、runtime permission boundary、runtime audit、runtime workspace alignment 和 WorkspaceManager alignment design 已完成收口。Phase 3.0 已完成 AgentScope RAG Service 架构对齐，Phase 3.1 已完成 RAG 配置骨架和安全状态展示，Phase 3.2 新增平台 KnowledgeBase metadata facade，Phase 3.3 新增 Document metadata facade，Phase 3.4 新增受控文件上传、本地解析和 Chunk registry，但尚未启用真实 RAG、Qdrant、embedding、BlobStore、index worker、Search 或 chat RAG。

平台主链路是：

```text
Tenant / User -> Credential -> Agent -> Session -> Chat -> SSE -> Message History -> Workspace -> Tool / Permission / Audit
```

Agent 是模板，Session 是运行状态。所有资源设计都围绕 `tenant_id`、`user_id`、`agent_id`、`session_id` 的隔离边界展开。

## 目录

- [项目定位](#项目定位)
- [项目结构](#项目结构)
- [架构概览](#架构概览)
- [已完成能力](#已完成能力)
- [核心接口](#核心接口)
- [本地开发](#本地开发)
- [ECS 部署](#ecs-部署)
- [验证和 smoke test](#验证和-smoke-test)
- [文档索引](#文档索引)
- [安全边界](#安全边界)
- [路线图](#路线图)

## 项目定位

- 项目名称：AgentScope Enterprise Multi-Tenant Agent Platform
- 技术基座：AgentScope 2.0.3 Agent Service
- 运行环境：Kylin Linux Advanced Server V10 (Halberd) ECS
- 开发方式：本地 VS Code 开发，通过 Git 同步到 ECS 部署
- 身份方式：第一阶段使用 `X-Tenant-ID` / `X-User-ID` 模拟身份，后续替换为 JWT / OAuth / 企业统一登录
- 暂不接入：HiMarket，后续作为 API Gateway / 应用市场方向接入

## 项目结构

```text
agent-platform/
├── backend/                 # FastAPI + AgentScope Agent Service 后端入口
│   ├── app/
│   │   ├── main.py          # create_app 接入点和平台路由挂载
│   │   ├── config.py        # 环境变量配置
│   │   ├── auth/            # X-Tenant-ID / X-User-ID 模拟身份
│   │   ├── platform/        # 平台 facade、工具、权限、审计、workspace、runtime governance
│   │   ├── tools/           # extra_agent_tools 工厂
│   │   ├── middlewares/     # extra_agent_middlewares 工厂
│   │   ├── workspace/       # WorkspaceManager 规划
│   │   ├── rag/             # RAG 配置和 KnowledgeBase metadata facade
│   │   ├── memory/          # Long-term Memory 配置预留
│   │   └── team/            # Agent Team 配置预留
│   └── requirements.txt
├── frontend/                # 前端规划文档，暂不实现复杂前端
├── deploy/                  # ECS、systemd、启动脚本和环境检查脚本
├── docs/                    # 架构、阶段设计、smoke test 和路线图文档
├── scripts/                 # 本地安全 smoke 脚本
├── .env.example             # 环境变量模板，不包含真实密钥
└── README.md                # 项目总览
```

## 架构概览

```text
Client / Demo / Future Frontend
        |
        | X-Tenant-ID / X-User-ID
        v
Platform API Facade (/api/platform/...)
        |
        | scoped_user_id = tenant_id:user_id
        v
AgentScope Agent Service
        |
        +--> RedisStorage
        +--> RedisMessageBus
        +--> LocalWorkspaceManager
        +--> extra_agent_tools
        +--> extra_agent_middlewares

Platform Governance Layer
        |
        +--> Workspace Resolver: tenant/user/agent/session
        +--> Tool Registry
        +--> Permission JSON
        +--> Audit / Trace JSONL
        +--> Runtime Tool Governance
```

企业侧推荐通过 `/api/platform/...` 调用平台封装接口。AgentScope 原生接口仍保留，用于底层调试和对照验证。

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

### Phase 2.2：AgentScope Native Alignment 设计

完成 AgentScope Tool / Permission / Workspace 原生能力对齐设计，明确哪些能力应该先作为平台 facade，哪些能力后续再映射到 AgentScope runtime。

### Phase 2.3.1：Tool metadata native alignment

Tool Registry 增加原生对齐元数据：

- `native_type`
- `native_ref`
- `enabled`
- `timeout_seconds`
- `input_schema`
- `default_timeout_seconds`

当前 `echo_tool`、`time_tool`、`slow_tool`、`runtime_echo_tool` 都是安全 mock 工具。

### Phase 2.3.2：extra_agent_tools adapter 设计和签名核验

核验 AgentScope 2.0.3 真实签名：

- `create_app(...)`
- `extra_agent_tools: Callable[[str, str, str], Awaitable[list[ToolBase]]]`
- `extra_agent_middlewares: Callable[[str, str, str], Awaitable[list[MiddlewareBase]]]`
- `FunctionTool`
- `PermissionRule`
- `WorkspaceManagerBase`
- `LocalWorkspaceManager`

本阶段只做设计和核验，不接 runtime adapter。

### Phase 2.3.3：extra_agent_tools adapter skeleton

实现默认关闭的 runtime tools adapter。默认配置下返回 `[]`，不影响 AgentScope chat 主链路。显式开启 mock mode 并配置 allow 后，才可注入安全 mock `runtime_echo_tool`。

### Phase 2.3.4：Runtime permission boundary

为 `runtime_echo_tool` 增加双层权限边界：

- 注入前 allow filter
- 执行时 permission re-check

删除 allow rule 后，即使 callable 已经构造，也会返回 `RUNTIME_PERMISSION_DENIED`。

### Phase 2.3.5：Runtime audit / tracing

为 `runtime_echo_tool` 增加 runtime audit/tracing。显式开启 runtime audit 后，success / denied / error 会写入 JSONL，包含：

- `trace_id`
- `event_type=runtime_tool_call`
- `source=agentscope_runtime`
- `status`
- `duration_ms`
- `error_code`

审计不记录用户输入全文。

### Phase 2.3.6：Runtime workspace alignment

runtime tool 注入前解析并创建平台隔离 workspace：

```text
WORKSPACE_BASEDIR / tenant_id / user_id / agent_id / session_id
```

runtime audit 增加：

- `workspace_path`
- `workspace_exists`
- `workspace_created`
- `workspace_isolation_strategy`

`runtime_echo_tool` 不读写 workspace 文件，也不把 `workspace_path` 返回给模型。

### Phase 2.3.7：Runtime full regression + WorkspaceManager alignment design

新增本地 smoke test 脚本：

```bash
python scripts/smoke_phase2_3_7_runtime_tools.py
```

核验 AgentScope `LocalWorkspaceManager` 当前本地 workdir 是 `basedir/agent_id`，而平台 resolver 是 `basedir/tenant_id/user_id/agent_id/session_id`。本阶段只记录边界和未来 `PlatformWorkspaceManager` 设计，不替换 AgentScope `LocalWorkspaceManager`。

Runtime tools 默认关闭：

```env
PLATFORM_ENABLE_RUNTIME_TOOLS=false
PLATFORM_RUNTIME_TOOLS_MODE=disabled
PLATFORM_ENABLE_RUNTIME_AUDIT=false
PLATFORM_RUNTIME_AUDIT_MODE=disabled
```

只有显式开启 mock mode，并且平台 permission JSON 存在 allow 规则时，才会注入安全 mock 工具 `runtime_echo_tool`。该工具不读写文件、不访问网络、不执行系统命令、不接 MCP / Skill / 企业系统。

### Phase 2.4：Runtime Tool Governance 收口

Phase 2.4 统一了 Phase 2 runtime governance 文档和 smoke test 入口。完整说明见 [docs/phase2_4-runtime-tool-governance-closure.md](docs/phase2_4-runtime-tool-governance-closure.md)。

本地 smoke test 入口：

```bash
python scripts/smoke_phase2_4_runtime_governance.py
```

该脚本复用 Phase 2.3.7 runtime smoke，使用临时 permission/audit/workspace 文件，不依赖真实 `.env`，不启动 server，不访问网络。

### Phase 3.0：RAG Service 架构对齐

Phase 3.0 已完成 AgentScope 2.0.3 RAG 能力核验和平台架构对齐设计。

已核验的 AgentScope RAG 能力包括：

- `create_app` 的 `knowledge_base_manager`、`knowledge_parsers`、`knowledge_chunker`、`blob_store`、`enable_index_worker` 参数
- `agentscope.rag.KnowledgeBase`
- `ParserBase` / `TextParser` / `PDFParser` / `PPTParser` / `ImageParser`
- `ChunkerBase` / `ApproxTokenChunker`
- `VectorStoreBase` / `QdrantStore`
- `CollectionPerKbManager`
- `LocalBlobStore` / `S3BlobStore`
- `RAGMiddleware`
- AgentScope 原生 `/knowledge_bases` router

Phase 3.0 不新增 RAG API，不启用 RAG runtime，不部署 Qdrant，不修改 `main.py` 主链路。后续 Phase 3.1 将先做 RAG config skeleton，并保持默认关闭。

### Phase 3.1：RAG Config Skeleton

Phase 3.1 新增 RAG 配置项、配置状态解析和 `/api/platform/overview` 能力展示。

新增配置：

```env
PLATFORM_ENABLE_RAG=false
PLATFORM_RAG_MODE=disabled
PLATFORM_RAG_NATIVE_BASE_URL=
PLATFORM_RAG_ISOLATION_STRATEGY=collection_per_kb
PLATFORM_RAG_ENABLE_INDEX_WORKER=false
```

`features.rag.effective_enabled` 表示真实 RAG runtime 是否已经接线。Phase 3.1 中它始终为 `false`，`features.rag.runtime_registered` 也始终为 `false`，即使 `PLATFORM_ENABLE_RAG=true`。这能保证配置实验不会误启用 KnowledgeBase、BlobStore、Qdrant 或 index worker。

Phase 3.1 固定规则：`PLATFORM_RAG_ENABLE_INDEX_WORKER=true` 会被判定为 `misconfigured`，并保持 `effective_enabled=false`、`runtime_registered=false`。

`backend/app/main.py` 显式向 AgentScope `create_app` 传入禁用状态的 RAG 参数：

```python
knowledge_base_manager=None
knowledge_parsers=None
knowledge_chunker=None
blob_store=None
enable_index_worker=False
```

没有向 `create_app` 注入真实 RAG 组件。AgentScope 原生 `/knowledge_bases` router 可能存在，但在没有 `knowledge_base_manager` 时预期返回 `503 Service Unavailable`。Phase 3.1 不注册 `/api/platform/knowledge-bases`。

Phase 3.1 离线 smoke test：

```bash
python scripts/smoke_phase3_1_rag_config.py
```

### Phase 3.2：KnowledgeBase Facade Skeleton

Phase 3.2 新增平台侧 KnowledgeBase metadata facade：

- `POST /api/platform/knowledge-bases`
- `GET /api/platform/knowledge-bases`
- `GET /api/platform/knowledge-bases/{kb_id}`
- `DELETE /api/platform/knowledge-bases/{kb_id}`

这些接口只管理本地 KB metadata registry，不调用 AgentScope 原生 `/knowledge_bases`，不创建真实 `KnowledgeBaseManager`，不创建向量 collection，不上传文档，不解析切块，不调用 embedding，不启动 index worker，也不接入 chat RAG。Phase 3.2 只提供创建、列表、详情和软删除，不提供 Update，也不提供完整 CRUD。

KB metadata 采用 owner-private 规则：

```text
tenant_id + owner_user_id
```

当前用户只能看到、查询、删除自己在当前 tenant 下创建的 KB。跨 tenant 或同 tenant 的其他 user 访问 detail/delete 时统一返回 `404 Not Found`，避免泄露资源存在性。删除是 soft delete，列表默认只返回 `active` 记录。

同一 tenant/user 当前允许创建同名 KB，不做唯一性约束或 409 冲突。

新增配置：

```env
PLATFORM_RAG_KB_REGISTRY_PATH=.cache/agent-platform/rag-kb-registry.json
```

该配置只控制 Phase 3.2 本地 metadata registry 文件位置，不代表真实 RAG runtime 已启用。默认 registry 位于 `.cache/`，已被 Git 忽略。registry JSON 包含 `version=1` 和 `knowledge_bases`，坏 JSON 或非法结构不会被静默覆盖。`features.rag.effective_enabled` 和 `features.rag.runtime_registered` 继续保持 `false`。

Phase 3.2 离线 smoke test：

```bash
python scripts/smoke_phase3_2_kb_facade.py
```

### Phase 3.3：Document Metadata Facade Skeleton

Phase 3.3 在 KnowledgeBase 下新增 Document metadata facade：

- `POST /api/platform/knowledge-bases/{kb_id}/documents`
- `GET /api/platform/knowledge-bases/{kb_id}/documents`
- `GET /api/platform/knowledge-bases/{kb_id}/documents/{document_id}`
- `DELETE /api/platform/knowledge-bases/{kb_id}/documents/{document_id}`

这些接口只登记和管理 Document metadata，不接收真实文件，不保存二进制，不调用 Parser / Chunker / Embedding / VectorStore，不调用 AgentScope 原生 Document API，也不接入 chat RAG。

Document 必须属于当前 tenant/user 下 active KnowledgeBase。跨 tenant、跨 user、错误 KB + 正确 Document、父 KB 已删除、Document 已删除或不存在时统一返回 404。

Document 运行时状态只有：

```text
registered
deleted
```

同一 tenant/user、同一 KB 下允许登记同名 Document，不做唯一性约束。

新增配置：

```env
PLATFORM_RAG_DOCUMENT_REGISTRY_PATH=.cache/agent-platform/rag-document-registry.json
```

Phase 3.3 离线 smoke test：

```bash
python scripts/smoke_phase3_3_document_facade.py
```

### Phase 3.4：Document File Upload, Parsing and Chunking Skeleton

Phase 3.4 新增：

- `POST /api/platform/knowledge-bases/{kb_id}/documents/{document_id}/upload`
- 本地安全文件保存
- SHA-256 校验
- TXT / Markdown / 文本型 PDF 解析
- deterministic character chunking
- Chunk local JSON registry

当前成功上传后的 Document 状态为：

```text
parsed
```

不是 `indexed` 或 `ready`。Chunk 还没有 Embedding，也没有写入向量数据库，因此平台仍不具备真实知识检索和 RAG 问答能力。

新增配置：

```env
PLATFORM_RAG_FILE_STORAGE_ROOT=.cache/agent-platform/rag-files
PLATFORM_RAG_CHUNK_REGISTRY_PATH=.cache/agent-platform/rag-chunk-registry.json
PLATFORM_RAG_MAX_UPLOAD_BYTES=10485760
PLATFORM_RAG_CHUNK_SIZE=1200
PLATFORM_RAG_CHUNK_OVERLAP=200
```

Phase 3.4 离线 smoke test：

```bash
python scripts/smoke_phase3_4_document_processing.py
```

## 核心接口

### 平台主链路接口

| 接口 | 说明 |
| --- | --- |
| `GET /api/platform/overview` | 查看平台能力概览 |
| `POST /api/platform/credentials` | 创建模型凭证 |
| `GET /api/platform/agents` | 查询当前租户/用户 Agent |
| `POST /api/platform/agents` | 创建 Agent 模板 |
| `GET /api/platform/sessions?agent_id=...` | 查询 Agent 的 Session |
| `POST /api/platform/sessions` | 创建 Session |
| `POST /api/platform/chat` | 发起异步 chat |
| `GET /api/platform/sessions/{session_id}/messages?agent_id=...` | 查询消息历史 |
| `GET /api/platform/sessions/{session_id}/stream-url?agent_id=...` | 返回原生 SSE 地址 |

### Workspace / Tool / Permission / Audit 接口

| 接口 | 说明 |
| --- | --- |
| `GET /api/platform/workspaces/resolve` | 解析或创建隔离 workspace |
| `GET /api/platform/workspaces/files` | 查询当前 session workspace 文件列表 |
| `POST /api/platform/workspaces/cleanup-preview` | workspace 清理预览 |
| `POST /api/platform/workspaces/cleanup` | workspace 安全清理，默认 dry run |
| `GET /api/platform/tools` | 查询平台工具注册表 |
| `POST /api/platform/tools/{tool_name}/invoke` | 平台主动调用工具 |
| `GET /api/platform/tool-permissions` | 查询当前租户/用户工具 allow 规则 |
| `POST /api/platform/tool-permissions` | 新增工具 allow 规则 |
| `DELETE /api/platform/tool-permissions/{rule_id}` | 删除工具 allow 规则 |
| `GET /api/platform/audit/tool-calls` | 查询工具调用审计 |

### KnowledgeBase metadata facade 接口

| 接口 | 说明 |
| --- | --- |
| `POST /api/platform/knowledge-bases` | 创建平台侧 KB metadata |
| `GET /api/platform/knowledge-bases` | 查询当前 tenant/user 的 active KB metadata |
| `GET /api/platform/knowledge-bases/{kb_id}` | 查询当前 tenant/user 的 KB metadata 详情 |
| `DELETE /api/platform/knowledge-bases/{kb_id}` | soft delete 当前 tenant/user 的 KB metadata |

### Document metadata facade 接口

| 接口 | 说明 |
| --- | --- |
| `POST /api/platform/knowledge-bases/{kb_id}/documents` | 登记 Document metadata |
| `GET /api/platform/knowledge-bases/{kb_id}/documents` | 查询当前 KB 下未删除 Document metadata |
| `GET /api/platform/knowledge-bases/{kb_id}/documents/{document_id}` | 查询 Document metadata 详情 |
| `DELETE /api/platform/knowledge-bases/{kb_id}/documents/{document_id}` | soft delete Document metadata |
| `POST /api/platform/knowledge-bases/{kb_id}/documents/{document_id}/upload` | 上传、解析并切分 Document |

### 健康检查和身份检查

| 接口 | 说明 |
| --- | --- |
| `GET /platform/health` | 平台健康检查 |
| `GET /api/me` | 查看当前 header 模拟身份 |

## 配置说明

真实 `.env` 不提交 Git，只提交 `.env.example`。常用配置包括：

```env
AGENT_SERVICE_PORT=8891
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
WORKSPACE_BASEDIR=/data/agent-platform/workspaces
AGENT_SERVICE_INTERNAL_BASE_URL=http://127.0.0.1:8891

PLATFORM_TOOL_PERMISSION_FILE=
PLATFORM_TOOL_AUDIT_LOG_FILE=logs/tool-calls-audit.jsonl
PLATFORM_TOOL_TRACE_LOG_FILE=logs/tool-calls-trace.jsonl
PLATFORM_ENABLE_RUNTIME_TOOLS=false
PLATFORM_RUNTIME_TOOLS_MODE=disabled
PLATFORM_ENABLE_RUNTIME_AUDIT=false
PLATFORM_RUNTIME_AUDIT_MODE=disabled

PLATFORM_ENABLE_RAG=false
PLATFORM_RAG_MODE=disabled
PLATFORM_RAG_NATIVE_BASE_URL=
PLATFORM_RAG_ISOLATION_STRATEGY=collection_per_kb
PLATFORM_RAG_ENABLE_INDEX_WORKER=false
PLATFORM_RAG_KB_REGISTRY_PATH=.cache/agent-platform/rag-kb-registry.json
PLATFORM_RAG_DOCUMENT_REGISTRY_PATH=.cache/agent-platform/rag-document-registry.json
PLATFORM_RAG_FILE_STORAGE_ROOT=.cache/agent-platform/rag-files
PLATFORM_RAG_CHUNK_REGISTRY_PATH=.cache/agent-platform/rag-chunk-registry.json
PLATFORM_RAG_MAX_UPLOAD_BYTES=10485760
PLATFORM_RAG_CHUNK_SIZE=1200
PLATFORM_RAG_CHUNK_OVERLAP=200
```





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

## 验证和 smoke test

语法检查：

```bash
python -m compileall backend/app
python -m compileall scripts
```

Phase 2 runtime governance smoke test：

```bash
python scripts/smoke_phase2_4_runtime_governance.py
```

该脚本不会启动 server，不访问网络，不依赖真实 `.env`，不会污染真实 `config` 或 `logs`。它会使用临时 permission、audit、trace、workspace 文件验证：

- runtime tools 默认关闭返回 `[]`
- 显式开启但无 allow 时仍返回 `[]`
- 显式开启且 allow 后可注入 `runtime_echo_tool`
- 删除 allow 后，已构造 callable 也会被拒绝
- success / denied runtime audit 正常写入
- audit 不记录输入全文
- workspace 字段完整
- tenantA / tenantB 隔离正常

Phase 3.1 RAG config skeleton smoke test：

```bash
python scripts/smoke_phase3_1_rag_config.py
```

该脚本不会启动 server，不访问网络，不读写真实 `.env`。它验证 RAG 默认关闭、显式请求时仍未接线、非法配置 fail closed，以及状态输出不泄露 RAG native base URL。

Phase 3.2 KnowledgeBase facade hardening smoke test：

```bash
python scripts/smoke_phase3_2_kb_facade.py
```

该脚本不会启动正式 server，不连接 Redis，不访问网络，不调用 AgentScope 原生 `/knowledge_bases`。它会用临时 registry 文件验证 KB metadata 的只读不建文件、创建、列表、详情、soft delete、同名允许、跨 tenant/user 404 隔离、坏 JSON fail closed、原子写入，以及 `main.py` 仍保持 RAG runtime 禁用参数。

Phase 3.3 Document metadata facade smoke test：

```bash
python scripts/smoke_phase3_3_document_facade.py
```

该脚本不会启动正式 server，不连接 Redis，不访问网络，不调用 AgentScope RAG 或 Document 原生 API。它会用临时 KB registry 和临时 Document registry 验证 Document metadata 的父 KB 校验、四层隔离、请求体注入保护、soft delete、同名允许、坏 JSON fail closed 和原子写入。

Phase 3.4 Document upload / parsing / chunking smoke test：

```bash
python scripts/smoke_phase3_4_document_processing.py
```

该脚本使用临时 KB registry、Document registry、Chunk registry 和文件存储目录，不读取真实 `.env`，不访问网络，不连接 Redis/Qdrant/Embedding。它验证 TXT/Markdown 上传解析、Chunk 生成、路径穿越保护、大小限制、状态冲突、tenant/user/KB/document 隔离、Chunk 删除标记和 RAG 不变量。当前本地未安装 `pypdf` 时，PDF 成功场景会明确跳过。

## 文档索引

### 架构和部署

- [docs/architecture.md](docs/architecture.md)：总体架构说明
- [docs/deployment-plan.md](docs/deployment-plan.md)：部署计划
- [docs/demo-script.md](docs/demo-script.md)：演示脚本
- [docs/mvp-checklist.md](docs/mvp-checklist.md)：MVP 验收清单
- [docs/roadmap.md](docs/roadmap.md)：路线图
- [deploy/ecs-kylin.md](deploy/ecs-kylin.md)：Kylin ECS 部署说明

### 阶段文档

- [docs/phase1_5-platform-api.md](docs/phase1_5-platform-api.md)：平台 API facade
- [docs/phase1-smoke-test.md](docs/phase1-smoke-test.md)：Phase 1 smoke test
- [docs/phase2-workspace-tool-permission.md](docs/phase2-workspace-tool-permission.md)：Workspace / Tool / Permission
- [docs/phase2_1-hardening.md](docs/phase2_1-hardening.md)：Phase 2.1 加固
- [docs/phase2_2-agentscope-native-alignment.md](docs/phase2_2-agentscope-native-alignment.md)：AgentScope 原生能力对齐设计
- [docs/phase2_3_1-tool-metadata.md](docs/phase2_3_1-tool-metadata.md)：工具元数据
- [docs/phase2_3_2-extra-agent-tools-adapter-design.md](docs/phase2_3_2-extra-agent-tools-adapter-design.md)：runtime adapter 设计和签名核验
- [docs/phase2_3_3-extra-agent-tools-skeleton.md](docs/phase2_3_3-extra-agent-tools-skeleton.md)：runtime adapter skeleton
- [docs/phase2_3_4-runtime-permission-boundary.md](docs/phase2_3_4-runtime-permission-boundary.md)：runtime 权限边界
- [docs/phase2_3_5-runtime-audit-middleware.md](docs/phase2_3_5-runtime-audit-middleware.md)：runtime audit/tracing
- [docs/phase2_3_6-runtime-workspace-alignment.md](docs/phase2_3_6-runtime-workspace-alignment.md)：runtime workspace 对齐
- [docs/phase2_3_7-runtime-tool-full-regression.md](docs/phase2_3_7-runtime-tool-full-regression.md)：runtime 全链路 smoke test / regression
- [docs/phase2_3_7-workspace-manager-alignment-design.md](docs/phase2_3_7-workspace-manager-alignment-design.md)：WorkspaceManager 对齐设计
- [docs/phase2_4-runtime-tool-governance-closure.md](docs/phase2_4-runtime-tool-governance-closure.md)：Phase 2 runtime governance 收口
- [docs/phase3_0-rag-service-architecture-alignment.md](docs/phase3_0-rag-service-architecture-alignment.md)：Phase 3.0 RAG Service 架构对齐
- [docs/phase3_1-rag-config-skeleton.md](docs/phase3_1-rag-config-skeleton.md)：Phase 3.1 RAG 配置 skeleton
- [docs/phase3_2-knowledge-base-facade-skeleton.md](docs/phase3_2-knowledge-base-facade-skeleton.md)：Phase 3.2 KnowledgeBase metadata facade
- [docs/phase3_3-document-metadata-facade-skeleton.md](docs/phase3_3-document-metadata-facade-skeleton.md)：Phase 3.3 Document metadata facade
- [docs/phase3_4-document-upload-parsing-chunking.md](docs/phase3_4-document-upload-parsing-chunking.md)：Phase 3.4 Document upload / parsing / chunking

## 安全边界

- 不提交真实 `.env`。
- 不在代码、日志、文档中写真实 API Key。
- runtime tools 默认关闭。
- runtime audit 默认关闭。
- 当前 runtime 工具只允许安全 mock `runtime_echo_tool`。
- 不接 shell、系统命令、文件删除、网络访问工具。
- 不接 MCP / Skill / 真实企业系统。
- 不实现 custom WorkspaceManager。
- 不启用真实 RAG runtime。
- RAG config skeleton 只展示状态，不创建 KnowledgeBaseManager、BlobStore、VectorStore 或 index worker。
- KnowledgeBase facade 只管理本地 metadata，不调用 AgentScope 原生 `/knowledge_bases`。
- 跨 tenant/user 的 KB detail/delete 统一返回 404，避免泄露资源存在性。
- Phase 3.2 不新增 RAG audit，不写入 tool audit 文件。
- Phase 3.3 不新增 Document/RAG audit，不写入 tool audit 文件。
- Document facade 只管理 metadata，不保存真实文件、文本、chunk、embedding、向量或文件路径。
- Phase 3.4 允许本地保存源文件和 Chunk text，但不生成 Embedding、不写向量库、不提供 Search API。
- 本地 JSON metadata registry 只适合 MVP 和单进程本地验证，不是多进程或多实例生产存储。
- 不把 RAG 直接做成 runtime tool。
- 不修改官方 AgentScope 源码。
- JSON permission/audit 文件不是生产级并发存储，只作为 MVP skeleton 和 smoke test / regression 基础。

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
- [x] Phase 3.0 完成 RAG Service 架构对齐设计。
- [x] Phase 3.1 接入 RAG config skeleton，默认关闭。
- [x] Phase 3.2 接入 KnowledgeBase facade skeleton。
- [x] Phase 3.3 接入 Document metadata facade skeleton。
- [x] Phase 3.4 接入 Document upload / parsing / chunking skeleton。
- [ ] Phase 4 接入 Long-term Memory。
- [ ] Phase 5 接入 Agent Team。

## 路线图

- Phase 0：环境和项目骨架。
- Phase 1：Agent Service 主链路。
- Phase 1.5：平台 API facade 和基础多租户隔离。
- Phase 2：Workspace + Tool + Permission + Audit。
- Phase 2.1：Permission Admin、Workspace 文件和清理、工具超时、结构化 tracing。
- Phase 2.2：AgentScope Native Alignment 设计。
- Phase 2.3.1：Tool metadata native alignment。
- Phase 2.3.2：extra_agent_tools adapter 设计和签名核验。
- Phase 2.3.3：extra_agent_tools adapter skeleton。
- Phase 2.3.4：Runtime permission boundary。
- Phase 2.3.5：Runtime audit / tracing。
- Phase 2.3.6：Runtime workspace alignment。
- Phase 2.3.7：Runtime full regression + WorkspaceManager alignment design。
- Phase 2.4：Runtime Tool Governance 收口。
- Phase 3.0：RAG Service 架构对齐和 AgentScope RAG 签名核验。
- Phase 3.1：RAG config skeleton，默认关闭。
- Phase 3.2：KnowledgeBase facade skeleton。
- Phase 3.3：Document metadata facade skeleton，不做真实上传。
- Phase 3.4：Document file upload, parsing and chunking skeleton，不做 Embedding/Search。
- Phase 3.5：Search facade + metadata_filter isolation。
- Phase 3.5：Agent-KB binding。
- Phase 3.6：RAG audit / tracing。
- Phase 3.7：RAG ECS smoke test。
- Phase 3.8：Chat RAG integration design。
- Phase 4：Long-term Memory。
- Phase 5：Agent Team。
- Phase 6：企业鉴权、审计、预算、限流、部署治理。
- Phase 7：HiMarket / API Gateway / 应用市场接入。

# RAG 模块说明

`backend/app/rag` 是 Phase 3 RAG Service 平台封装的预留目录。

当前状态：Phase 3.1 只完成 RAG 配置 skeleton、状态解析和安全能力展示，没有启用真实 RAG runtime，没有新增 KnowledgeBase API，也没有连接 Qdrant、embedding、BlobStore 或 index worker。

## 已有文件

- `config.py`：提供 `RagConfigStatus`、`resolve_rag_config_status(settings)` 和兼容函数 `build_rag_service_plan(settings)`。
- `README.md`：说明当前边界和后续模块规划。

## Phase 3.1 配置状态

当前支持解析：

- `PLATFORM_ENABLE_RAG`
- `PLATFORM_RAG_MODE`
- `PLATFORM_RAG_NATIVE_BASE_URL`
- `PLATFORM_RAG_ISOLATION_STRATEGY`
- `PLATFORM_RAG_ENABLE_INDEX_WORKER`

允许值：

- `PLATFORM_RAG_MODE`: `disabled`、`native_service`
- `PLATFORM_RAG_ISOLATION_STRATEGY`: `collection_per_kb`、`shared_collection_metadata_filter`

注意：`RagConfigStatus.effective_enabled` 表示真实 RAG runtime 是否已经接线。Phase 3.1 中它始终为 `false`，即使 `PLATFORM_ENABLE_RAG=true`。

状态值：

- `disabled`
- `configured_not_implemented`
- `misconfigured`

固定规则：`PLATFORM_RAG_ENABLE_INDEX_WORKER=true` 在 Phase 3.1 中必须进入 `misconfigured`，并保持 `effective_enabled=false`、`runtime_registered=false`。

## 后续建议模块

Phase 3.2+ 可以按小步增加：

- `schemas.py`：KnowledgeBase、Document、Search、Agent-KB binding 的平台 schema。
- `registry.py`：平台 KB metadata registry。
- `native_client.py`：封装 AgentScope 原生 `/knowledge_bases` 调用。
- `routes.py`：挂载 `/api/platform/knowledge-bases/...` facade。
- `permissions.py`：RAG 默认拒绝权限模型。
- `audit.py`：RAG audit/tracing JSONL。
- `bindings.py`：Agent-KB binding。

## 当前边界

- 不修改官方 AgentScope 源码。
- 不触碰真实 `.env`。
- 不部署 Qdrant。
- 不调用真实 embedding 服务。
- 不调用 AgentScope 原生 `/knowledge_bases`。
- 不实现 RAG upload/search/chat integration。
- 不把 RAG 直接做成 runtime tool。
- 不改变 Phase 1 / 1.5 / 2 的现有接口。

详细设计见：

- `docs/phase3_0-rag-service-architecture-alignment.md`
- `docs/phase3_1-rag-config-skeleton.md`

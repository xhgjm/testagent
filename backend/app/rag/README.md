# RAG 模块说明

`backend/app/rag` 是 Phase 3 RAG Service 平台封装的预留目录。

当前状态：Phase 3.4 已完成 RAG 配置 skeleton、状态解析、安全能力展示、平台侧 KnowledgeBase metadata facade、Document metadata facade、受控文件上传、本地解析和 Chunk registry。当前仍没有启用真实 RAG runtime，没有调用 AgentScope 原生 `/knowledge_bases` 或 Document API，也没有连接 Qdrant、embedding、BlobStore 或 index worker。

## 已有文件

- `config.py`：提供 `RagConfigStatus`、`resolve_rag_config_status(settings)` 和兼容函数 `build_rag_service_plan(settings)`。
- `schemas.py`：提供 Phase 3.2 KnowledgeBase metadata 请求和响应模型。
- `registry.py`：提供 owner-private 的本地 JSON metadata registry。
- `document_registry.py`：提供 Phase 3.3 Document metadata JSON registry。
- `file_storage.py`：提供 Phase 3.4 本地文件安全保存。
- `parsing.py`：提供 TXT / Markdown / 文本型 PDF 本地解析。
- `chunking.py`：提供 deterministic character chunker。
- `chunk_registry.py`：提供 Chunk local JSON registry。
- `document_processing.py`：编排上传、解析、切分和状态更新。
- `routes.py`：挂载 `/api/platform/knowledge-bases` facade。
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

`backend/app/main.py` 显式向 AgentScope `create_app` 传入禁用状态的 RAG 参数：

```python
knowledge_base_manager=None
knowledge_parsers=None
knowledge_chunker=None
blob_store=None
enable_index_worker=False
```

当前没有向 `create_app` 注入真实 RAG 组件。AgentScope 原生 `/knowledge_bases` router 可能存在，但在没有 `knowledge_base_manager` 时预期返回 `503 Service Unavailable`。

## Phase 3.2 KnowledgeBase metadata facade

Phase 3.2 新增平台入口：

```text
POST   /api/platform/knowledge-bases
GET    /api/platform/knowledge-bases
GET    /api/platform/knowledge-bases/{kb_id}
DELETE /api/platform/knowledge-bases/{kb_id}
```

这些接口只管理平台本地 KB metadata：

- 不调用 AgentScope 原生 `/knowledge_bases`。
- 不创建真实 AgentScope `KnowledgeBase`。
- 不创建 vector collection。
- 不上传文档。
- 不解析、切块、embedding。
- 不启动 index worker。
- 不接 chat RAG。

KB metadata 按 `tenant_id + owner_user_id` 私有隔离。当前用户只能看到和删除自己在当前 tenant 下创建的 KB。跨 tenant 或同 tenant 其他 user 的 detail/delete 统一返回 404，避免泄露资源存在性。

Phase 3.2 只提供创建、列表、详情和软删除，不提供 Update，也不提供完整 CRUD。同一 tenant/user 当前允许创建同名 KB。

本地 JSON registry 包含 `version=1` 和 `knowledge_bases`，写入使用同目录临时文件和 `os.replace`。坏 JSON 或非法结构不会被静默覆盖。进程内锁只保护单进程线程并发，不支持多进程、多 worker 或多实例生产部署。

Phase 3.2 不新增 RAG audit，也不把 KB metadata 操作写入现有 tool audit 文件。

## Phase 3.3 Document metadata facade

Phase 3.3 在同一个 router 上新增：

```text
POST   /api/platform/knowledge-bases/{kb_id}/documents
GET    /api/platform/knowledge-bases/{kb_id}/documents
GET    /api/platform/knowledge-bases/{kb_id}/documents/{document_id}
DELETE /api/platform/knowledge-bases/{kb_id}/documents/{document_id}
```

这些接口只登记和管理 Document metadata：

- 不接收真实文件。
- 不保存二进制、Base64、正文或真实文件路径。
- 不解析、不切块、不 embedding。
- 不创建向量索引。
- 不调用 AgentScope 原生 Document API。
- 不接 chat RAG。

Document 当前只有 `registered` 和 `deleted` 两种运行时状态。Document API 先校验父 KB 必须属于当前 tenant/user 且为 `active`，再校验 `document_id + knowledge_base_id + tenant_id + owner_user_id + status=registered`。错误 KB + 正确 Document、跨 tenant/user、父 KB 删除、Document 删除或不存在时统一返回 404。

Document registry 使用 `version=1` 和 `documents`，写入使用同目录临时文件、`flush`、`fsync` 和 `os.replace`。进程内锁只保护单进程线程并发，不支持多 worker、多进程或多实例生产部署。

Phase 3.3 不新增 Document/RAG audit，也不写入现有 tool audit 文件。

## Phase 3.4 Document upload / parsing / chunking

Phase 3.4 新增：

```text
POST /api/platform/knowledge-bases/{kb_id}/documents/{document_id}/upload
```

该接口只对已有 Document metadata 上传文件。处理流程：

```text
校验 KB active/owner
校验 Document owner/status
流式保存文件并计算 SHA-256
解析 TXT/Markdown/文本型 PDF
使用 local_character_v1 切分
写入 Chunk registry
更新 Document status=parsed
```

成功后 `parsed != indexed`，也不代表可 RAG 检索。当前 Chunk 没有 Embedding，没有 Vector ID，也没有 Search API。

支持类型：

- `text/plain`
- `text/markdown`
- `text/x-markdown`
- `application/pdf`

本地环境未安装 `pypdf` 时 PDF 会安全失败；依赖文件已加入 `pypdf`，ECS 安装依赖后可验证文本型 PDF。

Phase 3.4 不新增正式 RAG audit，也不写入现有 tool audit 文件。

## 后续建议模块

Phase 3.3+ 可以按小步增加：

- `native_client.py`：真实 runtime 接线后再封装 AgentScope 原生 `/knowledge_bases` 调用。
- `permissions.py`：RAG 默认拒绝权限模型。
- `audit.py`：RAG audit/tracing JSONL。
- `bindings.py`：Agent-KB binding。

## 当前边界

- 不修改官方 AgentScope 源码。
- 不触碰真实 `.env`。
- 不部署 Qdrant。
- 不调用真实 embedding 服务。
- 不调用 AgentScope 原生 `/knowledge_bases`。
- `/api/platform/knowledge-bases` 只管理 metadata，不代表 RAG runtime 已启用。
- `/api/platform/knowledge-bases/{kb_id}/documents` 只管理 Document metadata，不代表文件已上传或索引。
- `/api/platform/knowledge-bases/{kb_id}/documents/{document_id}/upload` 只做本地文件保存、解析和 Chunk，不代表已 embedding 或可 search。
- 不实现 RAG upload/search/chat integration。
- 不把 RAG 直接做成 runtime tool。
- 不改变 Phase 1 / 1.5 / 2 的现有接口。

详细设计见：

- `docs/phase3_0-rag-service-architecture-alignment.md`
- `docs/phase3_1-rag-config-skeleton.md`

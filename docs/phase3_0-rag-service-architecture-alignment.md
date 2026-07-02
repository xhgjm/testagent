# Phase 3.0：RAG Service Architecture Alignment with AgentScope RAG

## A. 本阶段目标

Phase 3.0 只做 AgentScope 2.0.3 RAG 能力核验和企业平台架构对齐设计。

本阶段不实现 RAG API，不部署 Qdrant，不接 embedding，不改 ECS，不触碰真实 `.env`，不修改官方 AgentScope 源码，也不改变当前 Agent Service / chat / session / message 主链路。

Phase 3 的原则是：AgentScope 提供 RAG building blocks 和 RAG Service，平台层负责企业 API facade、多租户隔离、权限、审计、元数据、Agent-KB 绑定和部署治理。

参考官方文档：

- https://docs.agentscope.io/versions/2.0.3/zh/building-blocks/rag
- https://docs.agentscope.io/versions/2.0.3/zh/deploy/rag

## B. 官方 RAG 能力理解

### Building Blocks / RAG

AgentScope 2.0.3 的 RAG building blocks 主要包含：

- Parser：把上传文件解析为结构化 section。
- Chunker：把 section 切分为可索引 chunk。
- Embedding Model：把 query / chunk 转为向量。
- Vector Store：存储向量和元数据，负责 similarity search。
- KnowledgeBase：封装 embedding model、vector store、collection 和 `metadata_filter`。
- RAGMiddleware：把多个 KnowledgeBase 暴露给 Agent runtime，使 Agent 可在对话中检索知识。

本地源码核验显示 `KnowledgeBase` 暴露：

- `search(...)`
- `insert_document(...)`
- `delete_document(...)`
- `list_documents(...)`

`metadata_filter` 是 RAG 隔离的关键防线之一。平台未来必须把 `tenant_id`、`kb_id` 等边界写入文档 metadata，并在 search / list / insert / delete 时保持过滤条件。

### Deploy / RAG Service

AgentScope Agent Service 的 `create_app(...)` 已内置 RAG Service 参数：

- `knowledge_base_manager`
- `knowledge_parsers`
- `knowledge_chunker`
- `blob_store`
- `enable_index_worker`

当 `knowledge_base_manager` 为 `None` 时，KB 能力不实际启用；当它存在时，AgentScope 会设置 parser / chunker / blob store，并根据 `enable_index_worker` 决定 API 进程是否启动内置 index worker。

当前 agent-platform Phase 3.1 中，`main.py` 显式传入禁用状态的 RAG 参数：

```python
knowledge_base_manager=None
knowledge_parsers=None
knowledge_chunker=None
blob_store=None
enable_index_worker=False
```

因此没有向 `create_app` 注入真实 RAG 组件，也不会启动 index worker。

本地源码确认原生 RAG router 挂载在：

```text
/knowledge_bases
```

已核验的原生能力包括：

- 查询 embedding models
- 查询 RAGMiddleware 参数 schema
- 查询支持的 content types
- 创建 / 列表 / 更新 / 删除 KnowledgeBase
- 上传 / 列表 / 查询状态 / 删除 Document
- 搜索 KnowledgeBase

Phase 3 平台不会直接把原生 `/knowledge_bases` 作为企业入口，而是在 `/api/platform/knowledge-bases` 上封装 facade。

## C. AgentScope 2.0.3 本地 API 核验结果

本地环境：

```text
agentscope version: 2.0.3
agentscope file: D:\ana\envs\agent-platform\Lib\site-packages\agentscope\__init__.py
```

`create_app` 导入路径：

```python
from agentscope.app import create_app
```

已核验 signature：

```text
create_app(
    storage,
    message_bus,
    workspace_manager,
    knowledge_base_manager=None,
    knowledge_parsers=None,
    knowledge_chunker=None,
    blob_store=None,
    enable_index_worker=True,
    *,
    extra_credentials=None,
    extra_middlewares=None,
    extra_agent_middlewares=None,
    extra_agent_tools=None,
    custom_subagent_templates=None,
    custom_agent_cls=None,
    title="AgentScope",
    version="2.0.3",
) -> Any
```

RAG 参数已确认存在：

| 参数 | 核验结果 |
| --- | --- |
| `knowledge_base_manager` | 存在，类型提示为 `KnowledgeBaseManagerBase | None` |
| `knowledge_parsers` | 存在，类型提示为 `list[ParserBase] | dict[str, ParserBase] | None` |
| `knowledge_chunker` | 存在，类型提示为 `ChunkerBase | None` |
| `blob_store` | 存在，类型提示为 `BlobStoreBase | None` |
| `enable_index_worker` | 存在，默认 `True`；当 manager 为 `None` 时无效 |

已核验导入路径和 signature：

```python
from agentscope.rag import KnowledgeBase
```

```text
KnowledgeBase(
    name: str,
    description: str,
    embedding_model,
    vector_store,
    collection: str,
    metadata_filter: dict | None = None,
)
```

```python
from agentscope.rag import ParserBase, TextParser, PDFParser, PPTParser, ImageParser
from agentscope.rag import ChunkerBase, ApproxTokenChunker
from agentscope.rag import VectorStoreBase, QdrantStore
```

```text
ParserBase.parse(file, filename)
TextParser(encoding="utf-8")
PDFParser()
PPTParser(include_image=True, separate_table=False, ...)
ImageParser()
ChunkerBase.chunk(sections)
ApproxTokenChunker(chunk_size=512, overlap=50)
QdrantStore(location=None, url=None, path=None, api_key=None, ...)
```

```python
from agentscope.app.rag.knowledge_base_manager import (
    KnowledgeBaseManagerBase,
    CollectionPerKbManager,
)
```

```text
KnowledgeBaseManagerBase(storage, vector_store)
CollectionPerKbManager(storage, vector_store)
create_knowledge_base(user_id, name, description, embedding_model_config)
get_knowledge_base(user_id, knowledge_base_id)
list_knowledge_bases(user_id)
delete_knowledge_base(user_id, knowledge_base_id)
```

```python
from agentscope.app.rag.blob_store import BlobStoreBase, LocalBlobStore, S3BlobStore
```

```text
BlobStoreBase.open(uri)
BlobStoreBase.write_stream(key, stream)
BlobStoreBase.exists(uri)
BlobStoreBase.delete(uri)
LocalBlobStore(root_dir)
S3BlobStore(bucket, ...)
```

```python
from agentscope.middleware import RAGMiddleware
```

```text
RAGMiddleware(knowledge_bases: list[KnowledgeBase], parameters=None)
```

原生 router 源码确认：

```text
agentscope.app._router._knowledge_base
prefix="/knowledge_bases"
```

原生 schema 核验：

```text
CreateKnowledgeBaseRequest: name, description, embedding_model_config
EmbeddingModelConfig: type, credential_id, model, dimensions, parameters
KnowledgeDocumentView: id, filename, size, content_type, status, error, chunk_count, created_at, updated_at
SearchKnowledgeBaseRequest: query, top_k
```

文档状态值核验：

```text
pending, parsing, chunking, indexing, ready, error
```

需要后续继续核验：

- AgentScope 原生 KB 是否已有 Agent/session 级 RAGMiddleware 自动绑定行为。
- `knowledge_bases` 字段在 session schema 中的最终请求体形状。
- 分布式 index worker 的生产部署命令和消息队列细节。
- S3 / OSS / MinIO 的推荐配置差异。

## D. 当前 agent-platform 状态盘点

已有能力：

- Phase 1：`backend.app.main:app` 通过 AgentScope `create_app` 启动。
- Phase 1.5：`/api/platform/...` facade，使用 `scoped_user_id = tenant_id:user_id` 调用 AgentScope 原生接口。
- Phase 2：workspace、tool registry、permission、audit。
- Phase 2.1：permission admin、workspace files / cleanup、tool timeout、structured tracing。
- Phase 2.3：runtime tool adapter、runtime permission、runtime audit、runtime workspace，默认全部关闭。
- Phase 2.4：runtime governance closure。
- `backend/app/rag/config.py`：已有 `RagConfigStatus(effective_enabled=False, runtime_registered=False, ...)` 配置骨架。
- `main.py`：已把 RAG 参数显式传给 `create_app`，真实组件当前均为 `None`，没有启用真实 RAG。
- Phase 3.1 更新：`main.py` 显式传入 `enable_index_worker=False`，并保持 `knowledge_base_manager=None`、`knowledge_parsers=None`、`knowledge_chunker=None`、`blob_store=None`。

缺失能力：

- 平台 RAG facade。
- KnowledgeBase registry / metadata。
- Document metadata。
- Agent-KB binding。
- RAG permission。
- RAG audit/tracing。
- 搜索接口。
- 上传 / indexing 状态 facade。
- Vector store / Blob store 真实部署。
- Chat RAG integration。

## E. Phase 3 平台 RAG Facade API 设计

企业用户未来应调用平台接口：

```text
GET    /api/platform/knowledge-bases
POST   /api/platform/knowledge-bases
GET    /api/platform/knowledge-bases/{kb_id}
DELETE /api/platform/knowledge-bases/{kb_id}

POST   /api/platform/knowledge-bases/{kb_id}/documents
GET    /api/platform/knowledge-bases/{kb_id}/documents
GET    /api/platform/knowledge-bases/{kb_id}/documents/{document_id}
DELETE /api/platform/knowledge-bases/{kb_id}/documents/{document_id}

POST   /api/platform/knowledge-bases/{kb_id}/search

POST   /api/platform/agents/{agent_id}/knowledge-bases
GET    /api/platform/agents/{agent_id}/knowledge-bases
DELETE /api/platform/agents/{agent_id}/knowledge-bases/{kb_id}
```

Facade 设计原则：

- 所有接口必须要求 `X-Tenant-ID` 和 `X-User-ID`。
- 平台层继续使用 `ScopedUser`。
- 调用 AgentScope 原生 RAG Service 时，内部 `X-User-ID` 使用 `tenant_id:user_id`。
- 对外不直接暴露底层 collection name，除非作为 debug metadata。
- 不能通过 body/query 伪造 `tenant_id` 或 `user_id`。
- 所有 list / get / search / delete 都必须加 tenant/user/kb 过滤。
- 原生 `/knowledge_bases` 保留用于底层调试，但不作为企业入口。

## F. KnowledgeBase 元数据设计

平台 KB metadata 建议字段：

```json
{
  "kb_id": "...",
  "tenant_id": "tenantA",
  "owner_user_id": "userA",
  "name": "企业制度知识库",
  "description": "...",
  "visibility": "private|tenant",
  "embedding_model": {
    "type": "openai_embedding_model",
    "credential_id": "...",
    "model": "...",
    "dimensions": 1536,
    "parameters": {}
  },
  "vector_store_type": "qdrant",
  "collection_name": "kb_...",
  "metadata_filter": {
    "tenant_id": "tenantA",
    "kb_id": "..."
  },
  "created_at": "...",
  "updated_at": "...",
  "status": "active|disabled|deleted",
  "native_kb_id": "...",
  "native_collection": "...",
  "isolation_strategy": "collection_per_kb_with_metadata_filter"
}
```

MVP 可以先用 JSON / RedisStorage / AgentScope 原生 storage 组合设计，生产环境应迁移到关系型数据库或可靠元数据服务。

安全要求：

- `kb_id` 不能由调用方指定租户前缀绕过。
- `collection_name` 由服务端生成或映射。
- `metadata_filter` 由服务端生成，不能信任请求体。
- 同名 KB 也必须按 tenant/user 隔离。

## G. Document 元数据设计

平台 Document metadata 建议字段：

```json
{
  "document_id": "...",
  "kb_id": "...",
  "tenant_id": "tenantA",
  "user_id": "userA",
  "filename": "policy.pdf",
  "content_type": "application/pdf",
  "size": 123456,
  "checksum": "sha256:...",
  "status": "uploaded",
  "index_status": "pending",
  "source_uri": null,
  "blob_key": "...",
  "chunk_count": 0,
  "error_code": null,
  "created_at": "...",
  "updated_at": "...",
  "native_document_id": "...",
  "metadata": {
    "tenant_id": "tenantA",
    "kb_id": "...",
    "document_id": "..."
  }
}
```

平台状态建议：

```text
uploaded -> parsing -> chunking -> embedding -> indexed
failed
deleted
```

AgentScope 原生状态核验为：

```text
pending, parsing, chunking, indexing, ready, error
```

平台可以映射为：

| 平台状态 | AgentScope 原生状态 |
| --- | --- |
| `uploaded` | `pending` |
| `parsing` | `parsing` |
| `chunking` | `chunking` |
| `embedding` | `indexing` |
| `indexed` | `ready` |
| `failed` | `error` |
| `deleted` | 平台软删除或原生 delete 成功 |

## H. 多租户隔离设计

平台层隔离：

- 所有 RAG facade 接口强制 `X-Tenant-ID` / `X-User-ID`。
- 内部 AgentScope 调用使用 `scoped_user_id = tenant_id:user_id`。
- KB metadata 必须保存 `tenant_id` 和 `owner_user_id`。
- Document metadata 必须保存 `tenant_id`、`user_id`、`kb_id`。
- Agent-KB binding 必须保存 `tenant_id`。
- list/get/search/delete 必须按当前 tenant/user 过滤。

RAG 层隔离：

- 优先采用 collection-per-kb。
- 每个 collection 仍要写入 `tenant_id`、`kb_id`、`document_id` metadata。
- `metadata_filter` 应至少包含 `tenant_id` 和 `kb_id`。
- search / list_documents 必须带 metadata filter。
- insert_document 时服务端强制写入 metadata filter 字段。
- delete_document 前必须校验 KB 和 Document 属于当前 tenant。

如果后续采用共享 collection：

- 必须强制 `metadata_filter`。
- 不允许请求体覆盖服务端 filter。
- 必须有独立 smoke test 验证 tenantA 不能检索 tenantB 文档。

## I. RAG Permission 设计

默认策略：deny。

建议动作：

- `kb:create`
- `kb:read`
- `kb:update`
- `kb:delete`
- `document:upload`
- `document:read`
- `document:delete`
- `rag:search`
- `agent_kb:bind`
- `agent_kb:unbind`

MVP 策略：

- KB 创建者默认拥有私有 KB 管理权限。
- tenant admin 可管理 tenant 范围 KB。
- Agent 绑定 KB 需要 `agent_kb:bind`。
- Search 需要 `rag:search`。
- Document upload/delete 需要显式权限。

实现方式建议：

- Phase 3.1/3.2 先定义 RAG permission schema，不接复杂 RBAC。
- 可复用 Phase 2 JSON permission 方式，但建议单独文件：`PLATFORM_RAG_PERMISSION_FILE`。
- 生产环境迁移到数据库和企业 IAM。

## J. RAG Audit / Tracing 设计

RAG audit JSONL 字段建议：

```json
{
  "trace_id": "...",
  "event_type": "rag_search",
  "source": "platform_rag_facade",
  "tenant_id": "tenantA",
  "user_id": "userA",
  "agent_id": "...",
  "session_id": "...",
  "kb_id": "...",
  "document_id": "...",
  "action": "rag:search",
  "status": "success|denied|error",
  "started_at": "...",
  "finished_at": "...",
  "duration_ms": 12,
  "error_code": null,
  "chunk_count": 5,
  "query_length": 28,
  "result_count": 3,
  "native_kb_id": "..."
}
```

建议事件类型：

- `rag_kb_create`
- `rag_kb_delete`
- `rag_document_upload`
- `rag_document_index`
- `rag_document_delete`
- `rag_search`
- `agent_kb_bind`
- `agent_kb_unbind`

安全要求：

- 默认不记录完整文档内容。
- 默认不记录完整 query，只记录长度、hash 或可配置摘要。
- 不记录 API Key、credential、Authorization。
- audit 查询必须按 tenant/user 过滤。

## K. Agent-KB Binding 设计

Agent 是模板，Session 是运行状态。RAG 绑定应先发生在 Agent 维度，再在 Session/chat 中生效。

绑定字段建议：

```json
{
  "tenant_id": "tenantA",
  "agent_id": "...",
  "kb_id": "...",
  "enabled": true,
  "retrieval_top_k": 5,
  "retrieval_mode": "manual_search|middleware",
  "created_at": "...",
  "updated_at": "..."
}
```

约束：

- Agent 和 KB 必须属于同一 tenant。
- userA 不能给 tenantB 的 Agent 绑定 KB。
- 删除 KB 时必须禁用或清理 binding。
- Phase 3.0 不实现 chat RAG。

建议顺序：

1. 先做 `/api/platform/knowledge-bases/{kb_id}/search`。
2. 再做 Agent-KB binding。
3. 最后设计 chat RAG integration。

## L. 与 Phase 2 Runtime Governance 的关系

RAG 不是 runtime tool governance 的替代品。

早期 Phase 3 不建议直接把 RAG search 暴露成 runtime tool。推荐先做平台 RAG facade，因为它更容易验证：

- tenant isolation
- permission
- audit
- upload / index 状态
- search metadata_filter

如果后续把 RAG search 做成 runtime tool，必须继承 Phase 2 的治理原则：

- 默认关闭。
- 注入前 permission filter。
- 执行时二次 permission check。
- runtime audit/tracing。
- workspace context。
- 不允许绕过平台 RAG facade 的 tenant filter。

## M. 部署设计

### Local / Dev

- 可使用 LocalBlobStore。
- 可使用 Qdrant `location=":memory:"` 或本地 Qdrant。
- 可使用单进程 index worker。
- 不承诺生产 SLA。
- 不写真实 API Key 到仓库。

### ECS smoke

- 继续使用端口 `8891`。
- Redis 继续作为 AgentScope storage / message bus。
- RAG 默认关闭。
- Phase 3.1 只加配置 skeleton。
- 后续如需 Qdrant，优先用 Docker 单实例验证。
- BlobStore 可先用 `/data/agent-platform/blobs`。
- smoke test 只验证最小 KB / upload / status / search，不做大文件压测。

### Production

- 使用对象存储：OSS / S3 / MinIO。
- 使用独立向量数据库：Qdrant / Milvus / 其他。
- 使用独立 index worker。
- 元数据进入数据库。
- 增加重试、失败恢复、索引状态、观测和告警。
- 增加企业鉴权、限流、配额和审计留存策略。

## N. Phase 3 分阶段计划

- Phase 3.1：RAG config skeleton，默认关闭。
- Phase 3.2：KnowledgeBase facade skeleton。
- Phase 3.3：Document metadata / upload facade skeleton。
- Phase 3.4：Search facade + metadata_filter isolation。
- Phase 3.5：Agent-KB binding。
- Phase 3.6：RAG audit/tracing。
- Phase 3.7：RAG ECS smoke test。
- Phase 3.8：Chat RAG integration design。

## O. 风险与限制

- 官方文档和本地包可能存在细微差异，实施前继续以本地 2.0.3 源码核验为准。
- RAG 可能引入额外依赖：Qdrant client、文件解析依赖、对象存储 SDK。
- Embedding 有成本、速率限制和凭证隔离问题。
- Vector store collection 隔离和 metadata_filter 配置错误会导致跨租户数据风险。
- 文档解析可能带来安全风险，尤其是 PDF/PPT/图片解析。
- 大文件上传需要大小限制、超时、病毒扫描和异步任务治理。
- 异步 indexing 可能出现状态不一致。
- 删除文档需要同时清理 blob、metadata、vector chunks。
- JSON 元数据不适合生产并发。
- Query 和文档内容都可能包含敏感信息，audit 必须谨慎。

## P. Phase 3.0 验收标准

- [x] 创建 Phase 3.0 RAG 架构对齐文档。
- [x] 核验 AgentScope 2.0.3 `create_app` RAG 参数。
- [x] 核验 `KnowledgeBase`、parser、chunker、blob store、Qdrant、RAGMiddleware 基本签名。
- [x] 确认原生 `/knowledge_bases` router 存在。
- [x] 盘点当前 `agent-platform` RAG 缺口。
- [x] 设计平台 RAG facade API。
- [x] 设计多租户 KB / Document / metadata_filter 隔离策略。
- [x] 设计 RAG permission 和 audit/tracing。
- [x] 明确 Phase 3.1+ 实施拆分。
- [x] 不修改 ECS。
- [x] 不修改官方 AgentScope 源码。
- [x] 不触碰真实 `.env`。
- [x] 不启用真实 RAG runtime。

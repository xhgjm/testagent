# Phase 3.3：Document Metadata Facade Skeleton

## 阶段目标

Phase 3.3 在 Phase 3.2 KnowledgeBase metadata facade 基础上，新增 KnowledgeBase 下的 Document metadata facade。

本阶段只建立文档与 `tenant_id`、`user_id`、`knowledge_base_id` 的安全归属关系。Document 当前只是 metadata 记录，不代表真实文件已经上传、解析、切分或建立向量索引。

## 当前边界

本阶段实现：

- Document metadata schema。
- Document 本地 JSON registry。
- Document 创建、列表、详情、软删除 API。
- 父 KnowledgeBase active/owner 校验。
- tenant/user/KB/Document 四层隔离。
- 请求体注入保护。
- 原子写入、进程内锁和损坏 JSON 保护。
- 离线 smoke test。

本阶段不实现：

- 真实文件上传。
- multipart/form-data。
- 文件二进制保存。
- BlobStore 或对象存储。
- Parser、OCR、Chunk、Embedding。
- VectorStore、Qdrant、Milvus、Elasticsearch。
- RAG search。
- Agent-KB binding。
- Chat RAG。
- AgentScope 原生 Document API 调用。
- RAG audit。

## 新增配置

```env
PLATFORM_RAG_DOCUMENT_REGISTRY_PATH=.cache/agent-platform/rag-document-registry.json
```

该配置只控制本地 Document metadata registry 文件位置。默认路径位于 `.cache/` 下，已被 Git 忽略。API 和 overview 不返回完整 registry 路径。

## Document 数据结构

创建请求只允许：

```json
{
  "name": "employee-handbook.pdf",
  "source_type": "file",
  "content_type": "application/pdf",
  "size_bytes": 102400
}
```

字段规则：

- `name` 去除首尾空格，不能为空，最长 255。
- `source_type` 当前只允许 `file`。
- `content_type` 去除首尾空格，不能为空，最长 255。
- `size_bytes` 必须是非负整数。
- 请求体禁止额外字段，不能伪造 `tenant_id`、`owner_user_id`、`document_id`、`knowledge_base_id`、`status`、`runtime_enabled`、`native_document_id`、`file_path` 等内部字段。

响应字段：

```json
{
  "document_id": "doc_xxx",
  "knowledge_base_id": "kb_xxx",
  "tenant_id": "tenantA",
  "owner_user_id": "userA",
  "created_by": "userA",
  "name": "employee-handbook.pdf",
  "source_type": "file",
  "content_type": "application/pdf",
  "size_bytes": 102400,
  "status": "registered",
  "runtime_enabled": false,
  "native_document_id": null,
  "created_at": "...",
  "updated_at": "...",
  "deleted_at": null
}
```

## Document 状态

Phase 3.3 运行时只产生：

- `registered`
- `deleted`

不产生 `uploaded`、`parsing`、`parsed`、`indexing`、`ready`。这些状态属于后续上传、解析、切块、索引阶段。

## API 列表

```text
POST   /api/platform/knowledge-bases/{kb_id}/documents
GET    /api/platform/knowledge-bases/{kb_id}/documents
GET    /api/platform/knowledge-bases/{kb_id}/documents/{document_id}
DELETE /api/platform/knowledge-bases/{kb_id}/documents/{document_id}
```

不提供 PUT/PATCH，不提供 Upload、Chunk、Search、Binding API。

## 父 KB 校验

所有 Document API 先通过 `KnowledgeBaseRegistry.get_for_owner(...)` 校验父 KB。

必须同时满足：

```text
kb_id 匹配
tenant_id 匹配
owner_user_id 匹配
status=active
```

以下情况统一返回 404：

- KB 不存在。
- KB 属于其他 tenant。
- KB 属于同 tenant 的其他 user。
- KB 已 soft delete。

不会返回真实 owner 或 tenant 信息。

## 四层隔离

Document detail/delete 必须同时匹配：

```text
document_id
knowledge_base_id
tenant_id
owner_user_id
status=registered
```

如果 `docA` 属于 `kbA`，使用 `kbB + docA` 查询或删除，即使 `kbA` 和 `kbB` 属于同一 tenant/user，也返回 404。

## Registry JSON

默认结构：

```json
{
  "version": 1,
  "documents": [
    {
      "document_id": "doc_xxx",
      "knowledge_base_id": "kb_xxx",
      "tenant_id": "tenantA",
      "owner_user_id": "userA",
      "created_by": "userA",
      "name": "employee-handbook.pdf",
      "source_type": "file",
      "content_type": "application/pdf",
      "size_bytes": 102400,
      "status": "registered",
      "runtime_enabled": false,
      "native_document_id": null,
      "created_at": "...",
      "updated_at": "...",
      "deleted_at": null
    }
  ]
}
```

只保存 metadata，不保存文件二进制、Base64、正文、Chunk、Embedding、向量、真实文件路径、BlobStore 凭据、API Key、Token、用户问题或模型回答。

## 写入和锁

Document registry 沿用 Phase 3.2 的本地 JSON 安全模式：

- 模块 import 和 Registry 初始化不创建文件。
- list/get 在文件不存在时返回空或 404，不创建文件。
- 首次成功 create 才创建目录和文件。
- delete 只有实际修改记录时才写文件。
- 写入使用同目录临时文件。
- 写入执行 `flush` 和 `fsync`。
- 最终使用 `os.replace` 原子替换。
- 使用模块级进程内锁覆盖完整 read-modify-write。

限制：

- 进程内锁只保护单进程线程并发。
- 本地 JSON registry 不支持多 worker、多进程、多实例生产部署。
- 后续生产应迁移到 PostgreSQL 或正式 metadata service。

## 损坏 JSON 保护

以下情况返回安全 500，且不覆盖原文件：

- 非法 JSON。
- `version != 1`。
- `documents` 不是 list。
- 关键字段缺失或类型错误。
- `status` 非 `registered/deleted`。
- `runtime_enabled != false`。
- `native_document_id != null`。

响应不返回完整路径、原始 JSON 内容或堆栈。

## soft delete

DELETE 成功返回：

```json
{
  "document_id": "doc_xxx",
  "knowledge_base_id": "kb_xxx",
  "status": "deleted",
  "deleted": true
}
```

删除后：

- registry 记录保留。
- `status=deleted`。
- `deleted_at` 被设置。
- list 不再返回。
- detail 返回 404。
- 再次 delete 返回 404。

本阶段没有真实文件，因此不会删除任何文件或 Blob。

## 同名策略

同一 tenant/user、同一个 KB 下允许登记同名 Document。不同 KB、tenant 或 user 也允许相同文档名称。本阶段不做唯一性约束，不返回 409。

## 为什么不上传文件

Phase 3.3 的目标是先把 tenant/user/KB/Document 的归属和访问边界做稳。上传文件会引入文件大小、内容类型、杀毒、对象存储、BlobStore、配额、审计和生命周期管理，本阶段故意不接入。

## 为什么不解析和切分

解析、切分、embedding 和索引涉及 Parser、Chunker、Embedding Model、VectorStore、Index Worker 和 RAG search。它们属于 Phase 3.4+，当前 runtime 仍保持关闭。

## 本地 smoke test

```powershell
D:\ana\envs\agent-platform\python.exe scripts/smoke_phase3_3_document_facade.py
```

脚本使用临时 KB registry 和临时 Document registry，不读取真实 `.env`，不连接 Redis/Qdrant/BlobStore/Embedding，不访问网络，不启动真实 RAG runtime。

覆盖：

- Python 3.11。
- 只读不创建 Document registry。
- 创建父 KB。
- 创建 Document metadata。
- 请求体注入保护。
- 字段校验。
- tenant/user 隔离。
- 错误 KB + 正确 Document 返回 404。
- 父 KB 删除后 Document API 返回 404。
- 同名 Document 允许。
- Document soft delete。
- 新 Registry 实例可读取持久化记录。
- 损坏 JSON 不覆盖。
- 临时文件、fsync、os.replace。
- OpenAPI route 方法检查。
- RAG 不变量。

## ECS 验收步骤

本阶段 Codex 不操作 ECS。同步后建议：

```bash
cd /app/agent-platform
git pull
D:\ana\envs\agent-platform\python.exe -c "import sys; print(sys.executable); print(sys.version)"
D:\ana\envs\agent-platform\python.exe -m compileall backend/app
D:\ana\envs\agent-platform\python.exe -m compileall scripts
D:\ana\envs\agent-platform\python.exe scripts/smoke_phase3_1_rag_config.py
D:\ana\envs\agent-platform\python.exe scripts/smoke_phase3_2_kb_facade.py
D:\ana\envs\agent-platform\python.exe scripts/smoke_phase3_3_document_facade.py
```

ECS Linux 上使用实际 Python 3.11 路径替换上述 Windows 解释器路径。

重启 8891 后验收：

1. `GET /api/platform/overview` 返回 `phase-3.3`。
2. 创建 KB。
3. 在 KB 下登记 Document。
4. tenantB 访问返回 404。
5. userB 访问返回 404。
6. 使用错误 `kb_id` 访问正确 `document_id` 返回 404。
7. soft delete Document。
8. 创建一个未删除 Document。
9. 重启 8891。
10. 重启后 KB 和未删除 Document 仍可查询。
11. AgentScope 原生 `/knowledge_bases` 继续 disabled/503。
12. Chat 主链路回归正常。

## Phase 3.4 建议

Phase 3.4 建议仍保持真实 RAG runtime 默认关闭，优先设计 Search facade 和 metadata_filter isolation：

- 定义 search request/response schema。
- 设计 `tenant_id + kb_id + document_id` metadata_filter。
- 设计 RAG permission 和 audit。
- 仍不急于接入 chat RAG。

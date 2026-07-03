# Phase 3.4：Document File Upload, Parsing and Chunking Skeleton

## 目标

Phase 3.4 在 Phase 3.3 Document metadata facade 基础上，新增受控文件上传、本地保存、离线解析和 deterministic chunking。

链路：

```text
KnowledgeBase -> Document metadata -> 上传源文件 -> 解析纯文本 -> 切分 Chunks -> 保存 Chunk 数据
```

本阶段最终状态是 `parsed`，不是 `indexed` 或 `ready`。当前仍没有 Embedding、向量索引、Search、Agent-KB binding 或 Chat RAG。

## 与 Phase 3.3 的区别

Phase 3.3 只登记 Document metadata。Phase 3.4 开始允许对已登记的 Document 上传真实小文件，并同步解析和切分。

仍然不做：

- OCR。
- Office 文档解析。
- 异步任务队列。
- BlobStore。
- Embedding。
- Vector index。
- Search。
- Agent-KB binding。
- Chat RAG。

## 上传 API

```text
POST /api/platform/knowledge-bases/{kb_id}/documents/{document_id}/upload
```

Content-Type：

```text
multipart/form-data
```

表单字段：

```text
file
```

上传前必须先通过 Phase 3.3 API 创建 Document metadata。上传成功返回 `DocumentResponse`，其中：

```text
status=parsed
chunk_count>0
checksum_sha256 非空
parser_name 非空
chunker_name=local_character_v1
uploaded_at 非空
parsed_at 非空
runtime_enabled=false
native_document_id=null
```

## 两步流程

本阶段采用：

```text
创建 Document metadata -> 上传文件
```

不提供“一步创建并上传”接口。这样可以先稳定 tenant/user/KB/Document 的归属边界，再处理文件安全、大小限制、解析和 chunk 持久化。

## 支持类型

支持：

- `text/plain`
- `text/markdown`
- `text/x-markdown`
- `application/pdf`

PDF 仅支持包含可提取文本层的普通 PDF。扫描 PDF、加密 PDF、图片型 PDF 不做 OCR。

## 文件大小限制

默认：

```env
PLATFORM_RAG_MAX_UPLOAD_BYTES=10485760
```

超过限制返回：

```text
413 DOCUMENT_TOO_LARGE
```

实际读取字节数必须等于 Document metadata 中登记的 `size_bytes`，否则返回：

```text
409 DOCUMENT_SIZE_MISMATCH
```

## 文件路径安全

配置：

```env
PLATFORM_RAG_FILE_STORAGE_ROOT=.cache/agent-platform/rag-files
```

文件路径由服务端生成。上传文件名不参与目录拼接，只用于判断安全扩展名。tenant/user 路径段使用稳定 SHA-256 hash，避免直接信任 header。

保存结构：

```text
rag-files/<tenant_hash>/<user_hash>/<kb_id>/<document_id>/source.<ext>
```

保存前确认最终路径仍位于 storage root 下，防止 `../` 路径穿越。API 不返回 `storage_key`、storage root 或绝对路径。

## 流式写入和 SHA-256

上传写入顺序：

```text
创建目标目录
写同目录临时文件
分块读取 UploadFile
边读边检查大小
边读边计算 SHA-256
flush
fsync
os.replace 到最终文件
```

不会使用 `await file.read()` 一次性读取大文件。

## Document 状态机

允许状态：

```text
registered
uploaded
parsing
parsed
failed
deleted
```

成功路径：

```text
registered -> uploaded -> parsing -> parsed
```

失败路径：

```text
registered/uploaded/parsing -> failed
```

删除路径：

```text
registered/uploaded/parsing/parsed/failed -> deleted
```

允许上传状态：

- `registered`
- `failed`

以下状态重复上传返回 409：

- `uploaded`
- `parsing`
- `parsed`
- `deleted` 返回 404

`parsed` 只有在源文件保存成功且 Chunk registry 写入成功后才设置。

## Parser

### TXT Parser

- UTF-8 / UTF-8-SIG 解码。
- 统一换行。
- 去除 NUL。
- 空文本失败。
- `parser_name=plain_text_utf8`。

### Markdown Parser

- UTF-8 / UTF-8-SIG 解码。
- 保留标题和段落。
- 统一换行。
- 去除 NUL。
- `parser_name=markdown_text_utf8`。

### PDF Parser

- 使用本地 `pypdf`。
- 验证 `%PDF-` 文件头。
- 按页提取文本。
- 空页面忽略。
- 无可提取文本失败。
- 加密 PDF 失败。
- 不调用 OCR、不访问网络。
- `parser_name=pypdf_text`。

如果本地环境未安装 `pypdf`，PDF 上传会安全失败；依赖文件已加入 `pypdf`，ECS 同步依赖后再执行 PDF 成功场景。

## Chunker

Phase 3.4 使用平台本地 deterministic character chunker：

```text
chunker_name=local_character_v1
```

配置：

```env
PLATFORM_RAG_CHUNK_SIZE=1200
PLATFORM_RAG_CHUNK_OVERLAP=200
```

约束：

```text
chunk_size > 0
0 <= chunk_overlap < chunk_size
```

行为：

- 统一换行和空白。
- 优先在段落/换行/句号边界切分。
- 找不到边界时按字符长度切分。
- 不产生空 Chunk。
- sequence 稳定连续。
- 不调用 tokenizer、模型或网络服务。

本阶段没有使用 AgentScope `ApproxTokenChunker`，因为当前目标是最小离线 skeleton，避免 runtime 和签名差异风险。

## Chunk 数据模型

```json
{
  "chunk_id": "chunk_xxx",
  "document_id": "doc_xxx",
  "knowledge_base_id": "kb_xxx",
  "tenant_id": "tenantA",
  "owner_user_id": "userA",
  "sequence": 0,
  "text": "chunk text",
  "char_count": 1200,
  "checksum_sha256": "...",
  "status": "active",
  "created_at": "..."
}
```

Chunk 不包含 Embedding、Vector ID、搜索分数或模型信息。

## Chunk Registry

配置：

```env
PLATFORM_RAG_CHUNK_REGISTRY_PATH=.cache/agent-platform/rag-chunk-registry.json
```

结构：

```json
{
  "version": 1,
  "chunks": []
}
```

内部能力：

- `replace_document_chunks(...)`
- `list_document_chunks(...)`
- `mark_document_chunks_deleted(...)`

写入使用共享进程锁、同目录临时文件、flush、fsync、`os.replace`。当前不提供公共 Chunk API。

## Document Registry v1 兼容

Phase 3.4 将 Document registry 写入版本升级为 `version=2`，新增：

- `storage_key`
- `checksum_sha256`
- `parser_name`
- `chunker_name`
- `chunk_count`
- `uploaded_at`
- `parsed_at`
- `error_code`

读取 `version=1` 时在内存中补默认值。只读不会改写原文件；下一次 mutation 才写成 `version=2`。

## 错误模型

- `404`：KB/Document 不存在、越权、错误 KB、已删除。
- `409 DOCUMENT_STATE_CONFLICT`：当前状态不允许上传。
- `409 DOCUMENT_SIZE_MISMATCH`：实际大小和登记大小不一致。
- `413 DOCUMENT_TOO_LARGE`：超过最大上传大小。
- `415 UNSUPPORTED_DOCUMENT_TYPE`：类型不支持。
- `422 INVALID_TEXT_ENCODING`：非法 UTF-8。
- `422 INVALID_DOCUMENT_CONTENT`：空文本或非法内容。
- `422 NO_EXTRACTABLE_TEXT`：PDF 无可提取文本。
- `500 DOCUMENT_STORAGE_FAILED`：文件保存失败。
- `500 DOCUMENT_PARSE_FAILED`：非预期解析失败。
- `500 CHUNK_REGISTRY_FAILED`：Chunk registry 写入失败。

错误响应不包含绝对路径、堆栈、原始 PDF 内容、Chunk text 或 registry 内容。

## 多租户隔离

上传前先校验父 KB：

```text
kb_id + tenant_id + owner_user_id + status=active
```

再校验 Document：

```text
document_id + knowledge_base_id + tenant_id + owner_user_id + status
```

tenantB 上传 tenantA Document、userB 上传 userA Document、错误 KB + 正确 Document、父 KB 已删除、Document 已删除都返回 404。

## 同步处理限制

上传、解析、切分当前同步执行，只适合小文件和开发验证。大文件和生产环境应改为异步任务、队列和 worker。

本地 JSON 与本地文件系统不是生产级事务。当前采用补偿式清理和失败状态，后续迁移数据库和对象存储后再做正式事务。

## 为什么仍未实现 Embedding 和 Search

Chunk 只是文本切片，尚未生成 Embedding，也未写入向量数据库。因此当前不具备真实知识检索，也不具备 RAG 问答能力。

## 本地 smoke

```powershell
D:\ana\envs\agent-platform\python.exe scripts/smoke_phase3_4_document_processing.py
```

Smoke 使用临时 KB registry、Document registry、Chunk registry 和文件存储目录，不读取真实 `.env`，不访问网络，不连接 Redis/Qdrant/Embedding，不启动 index worker。

当前本地环境未安装 `pypdf` 时，PDF 成功场景会明确跳过，不伪造结论。

## ECS 验收步骤

本阶段 Codex 不操作 ECS。建议：

1. `git pull`。
2. 检查 Python 3.11。
3. 安装或同步新增依赖 `python-multipart`、`pypdf`。
4. 执行 `compileall`。
5. 执行 Phase 3.1～3.4 smoke。
6. 设置文件存储和 Chunk registry 配置。
7. 重启 8891。
8. 验证 overview 为 `phase-3.4`。
9. 创建 KB。
10. 创建 registered Document。
11. 上传 TXT 文件。
12. 验证 `status=parsed`、`chunk_count>0`。
13. 验证源文件和 Chunk registry 持久化。
14. tenantB 上传返回 404。
15. 错误 KB + 正确 Document 返回 404。
16. 重启 8891。
17. 重启后 Document parsed 状态和 Chunk 数据仍存在。
18. AgentScope 原生 `/knowledge_bases` 继续 disabled/503。
19. Chat 主链路继续正常。

不要使用真实企业文档做 ECS 验收。

## Phase 3.5 建议

Phase 3.5 建议进入 Search facade + metadata_filter isolation 设计或实现：

- 设计只读 search API。
- 设计 tenant/user/KB/document metadata_filter。
- 引入 Embedding 和 VectorStore 前先完成 permission/audit 边界。
- 仍不急于接 Chat RAG。

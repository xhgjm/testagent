# Phase 3.2：KnowledgeBase Facade Skeleton

## 阶段目标

Phase 3.2 在 Phase 3.1 RAG Config Skeleton 基础上，新增企业平台侧 KnowledgeBase metadata facade。

本阶段只做平台本地 metadata 管理：

- 创建 KnowledgeBase metadata。
- 查询当前 tenant/user 的 KnowledgeBase metadata 列表。
- 查询当前 tenant/user 的 KnowledgeBase metadata 详情。
- soft delete 当前 tenant/user 的 KnowledgeBase metadata。

本阶段继续不启用真实 RAG runtime。

Phase 3.2 只提供创建、列表、详情和软删除，不提供 Update，也不提供完整 CRUD。

## 路径边界

Phase 3.2 明确区分两条链路：

```text
/api/platform/knowledge-bases
  -> 平台 KnowledgeBase metadata facade
  -> X-Tenant-ID / X-User-ID
  -> tenant_id + owner_user_id 私有隔离
  -> 本地 JSON metadata registry
```

```text
/knowledge_bases
  -> AgentScope 原生 KnowledgeBase route
  -> 当前 knowledge_base_manager=None
  -> 可能出现在 OpenAPI
  -> 访问时预期返回 503 Service Unavailable
```

平台代码不会调用 AgentScope 原生 `/knowledge_bases`。原生路由是否出现在 OpenAPI 不作为 Phase 3.2 的失败条件。

## 新增配置

```env
PLATFORM_RAG_KB_REGISTRY_PATH=.cache/agent-platform/rag-kb-registry.json
```

该配置只控制平台本地 KB metadata registry 文件位置。它不代表真实 RAG runtime 已启用，也不会影响：

- `features.rag.effective_enabled`
- `features.rag.runtime_registered`
- `enable_index_worker`

默认路径位于 `.cache` 下，仓库不会提交真实 metadata 文件。

## API 列表

### POST /api/platform/knowledge-bases

请求体：

```json
{
  "name": "Enterprise KB",
  "description": "metadata only"
}
```

规则：

- `name` 必填，去除首尾空格后不能为空，长度限制为 1 到 100。
- `description` 可选，最长 1000。
- 客户端不得传 `tenant_id`、`owner_user_id`、`scoped_user_id`、`native_kb_id`、`native_collection` 等内部字段。
- 内部字段来自 `X-Tenant-ID` 和 `X-User-ID`。
- `kb_id` 由服务端生成，格式为 `kb_<uuid hex>`。
- 只写入本地 metadata registry。
- 不调用 AgentScope 原生 `/knowledge_bases`。
- 同一 tenant/user 允许创建同名 KB，不返回 409。

响应示例：

```json
{
  "kb_id": "kb_xxx",
  "tenant_id": "tenantA",
  "owner_user_id": "userA",
  "scoped_user_id": "tenantA:userA",
  "name": "Enterprise KB",
  "description": "metadata only",
  "status": "active",
  "runtime_enabled": false,
  "native_kb_id": null,
  "native_collection": null,
  "isolation_strategy": "collection_per_kb",
  "created_at": "2026-07-02T00:00:00+00:00",
  "updated_at": "2026-07-02T00:00:00+00:00",
  "deleted_at": null
}
```

### GET /api/platform/knowledge-bases

只返回当前 `tenant_id + owner_user_id` 下 `active` 状态的 KB metadata：

```json
{
  "items": [],
  "total": 0
}
```

当前不实现分页，列表按 `created_at` 倒序返回。

### GET /api/platform/knowledge-bases/{kb_id}

只允许当前 owner 查询自己的 active KB。以下情况统一返回 `404 Not Found`：

- KB 不存在。
- KB 已 soft delete。
- KB 属于同 tenant 的其他 user。
- KB 属于其他 tenant。

这样可以避免泄露资源存在性和归属信息。

### DELETE /api/platform/knowledge-bases/{kb_id}

只允许当前 owner soft delete 自己的 active KB。删除后：

- `status=deleted`
- `deleted_at` 被设置
- `updated_at` 被更新
- list 不再返回该记录
- detail 返回 404
- 不删除任何真实向量 collection
- 不调用 AgentScope 原生 delete

## Metadata 字段

Phase 3.2 metadata 字段：

- `kb_id`：服务端生成。
- `tenant_id`：来自 `X-Tenant-ID`。
- `owner_user_id`：来自 `X-User-ID`。
- `scoped_user_id`：`tenant_id:user_id`，用于和平台隔离模型对齐。
- `name`：用户输入名称。
- `description`：用户输入描述。
- `status`：`active` 或 `deleted`。
- `runtime_enabled`：Phase 3.2 固定为 `false`。
- `native_kb_id`：Phase 3.2 固定为 `null`。
- `native_collection`：Phase 3.2 固定为 `null`。
- `isolation_strategy`：记录 Phase 3.1 RAG 配置中的隔离策略，仅作为设计 hint。
- `created_at` / `updated_at` / `deleted_at`：UTC ISO 8601 时间。

## 隔离策略

Phase 3.2 采用 owner-private 语义：

```text
tenant_id + owner_user_id
```

当前没有 tenant admin、共享 KB、跨用户可见性和 RAG permission admin。后续如需共享，应在 Phase 3.x 单独设计权限模型，不复用简单 owner-private 规则。

## Registry 行为

本阶段使用本地 JSON 文件保存 metadata：

- 只有 create/delete 会写文件。
- list/get 在文件不存在时返回空或 404。
- 写入使用临时文件加 `os.replace`。
- 使用进程内 `RLock` 降低单进程并发风险。
- JSON 损坏时不会覆盖成空文件。
- 非法 `version`、非法顶层结构、`knowledge_bases` 非 list 或关键字段损坏时不会覆盖原文件。
- JSON 损坏时 API 返回安全 500，不泄露文件路径。
- registry JSON 包含 `version=1` 和 `knowledge_bases`。

限制：

- JSON registry 不是生产级多实例存储。
- 多进程并发写仍可能存在风险。
- 后续生产环境应迁移到数据库或 AgentScope RAG Service 的正式 metadata 管理能力。

## Overview 字段

`GET /api/platform/overview` 在 Phase 3.2 中追加：

```json
{
  "knowledge_base_facade_registered": true,
  "knowledge_base_metadata_registry": true,
  "knowledge_base_registry": "local_json_metadata_only",
  "knowledge_base_facade": "metadata_only_owner_private",
  "knowledge_base_runtime_enabled": false,
  "knowledge_base_runtime_connected": false,
  "knowledge_base_native_calls": false,
  "knowledge_base_native_api_called": false
}
```

同时继续保持：

```json
{
  "rag_effective_enabled": false,
  "rag_runtime_registered": false
}
```

overview 不返回 registry 文件路径、不返回 RAG native base URL 原文、不返回用户文档内容。

## 安全边界

Phase 3.2 不做：

- 不修改官方 AgentScope 源码。
- 不修改真实 `.env`。
- 不修改 ECS。
- 不部署 Qdrant、Milvus、Elasticsearch 或其他向量库。
- 不调用 embedding 服务。
- 不实例化 KnowledgeBaseManager。
- 不实例化 BlobStore。
- 不实例化 VectorStore。
- 不启动 index worker。
- 不调用 AgentScope 原生 `/knowledge_bases`。
- 不实现 Document 上传、解析、切块、索引。
- 不实现 search。
- 不实现 Agent-KB binding。
- 不改 `/api/platform/chat`。
- 不实现 RAG runtime tool。
- 不新增 RAG audit，不写入现有 tool audit 文件。
- 不接 MCP / Skill / Memory / Agent Team / 前端。

`backend/app/main.py` 必须继续保持：

```python
knowledge_base_manager=None
knowledge_parsers=None
knowledge_chunker=None
blob_store=None
enable_index_worker=False
```

`enable_index_worker` 不能绑定到 `settings.platform_rag_enable_index_worker`。

## 本地 smoke test

语法检查：

```bash
python -m compileall backend/app
python -m compileall scripts
```

Phase 3.1 回归：

```bash
python scripts/smoke_phase3_1_rag_config.py
```

Phase 3.2 KB facade：

```bash
python scripts/smoke_phase3_2_kb_facade.py
```

脚本验证：

- `/api/platform/knowledge-bases` 路由已注册。
- `/api/platform/knowledge-bases/{kb_id}` 路由已注册。
- 平台 KB route 没有 PUT/PATCH，也没有 Document/Search/Binding 子路由。
- registry 不存在时 list/get 不创建文件。
- 缺少 header 返回 400。
- 客户端伪造内部字段返回 422。
- 空名称、纯空格名称、超长名称和超长描述返回 422。
- tenantA/userA 可以创建、查询、删除自己的 KB metadata。
- 同一 tenant/user 创建同名 KB 成功。
- tenantA/userB 和 tenantB/userA 看不到 tenantA/userA 的 KB。
- 跨 owner detail/delete 返回 404。
- 重复删除和不存在删除返回 404。
- soft delete 后列表不返回、详情返回 404。
- registry JSON 损坏、非法 version、非法结构、关键字段损坏时返回安全 500，且不覆盖损坏文件。
- registry 写入使用同目录临时文件和 `os.replace`。
- overview 不泄露 registry 路径。
- `main.py` 仍保持 RAG runtime 禁用参数。
- KB facade 代码不调用 AgentScope 原生 `/knowledge_bases`。

## ECS smoke test 设计

本阶段 Codex 不直接操作 ECS。同步到 ECS 后建议：

```bash
cd /app/agent-platform
git pull
python -m compileall backend/app
python -m compileall scripts
python scripts/smoke_phase3_1_rag_config.py
python scripts/smoke_phase3_2_kb_facade.py
```

重启 8891 后：

```bash
curl -s http://127.0.0.1:8891/platform/health | python -m json.tool
```

查看 overview：

```bash
curl -s \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  http://127.0.0.1:8891/api/platform/overview \
  | python -m json.tool
```

预期：

- `phase=phase-3.2`
- `knowledge_base_facade_registered=true`
- `knowledge_base_metadata_registry=true`
- `rag_effective_enabled=false`
- `rag_runtime_registered=false`

创建 KB metadata：

```bash
curl -s -X POST "http://127.0.0.1:8891/api/platform/knowledge-bases" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  -d '{"name":"Enterprise KB","description":"metadata only"}' \
  | tee /tmp/platform_kb.json | python -m json.tool
```

提取 KB_ID：

```bash
export KB_ID=$(python - <<'PY'
import json
d = json.load(open("/tmp/platform_kb.json"))
print(d["kb_id"])
PY
)
```

查询列表：

```bash
curl -s \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  http://127.0.0.1:8891/api/platform/knowledge-bases \
  | python -m json.tool
```

跨用户隔离：

```bash
curl -s \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userB" \
  "http://127.0.0.1:8891/api/platform/knowledge-bases/${KB_ID}" \
  | python -m json.tool
```

预期返回 404。

soft delete：

```bash
curl -s -X DELETE \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  "http://127.0.0.1:8891/api/platform/knowledge-bases/${KB_ID}" \
  | python -m json.tool
```

确认原生 route 没有被平台调用；原生 `/knowledge_bases` 可能在 OpenAPI 出现，但当前没有 `knowledge_base_manager`，访问时预期为禁用态。

## 当前限制

- 当前只管理 KB metadata。
- 不支持同名唯一性约束。
- 不支持分页。
- 不支持 shared KB。
- 不支持 tenant admin。
- 不支持 Document metadata。
- 不支持文件上传。
- 不支持 search。
- 不支持 Agent-KB binding。
- 不支持 RAG audit。
- JSON registry 不是生产存储。

## Phase 3.3 建议

Phase 3.3 建议继续保持真实 RAG runtime 默认关闭，只增加 Document metadata / upload facade skeleton：

- `POST /api/platform/knowledge-bases/{kb_id}/documents`
- `GET /api/platform/knowledge-bases/{kb_id}/documents`
- `GET /api/platform/knowledge-bases/{kb_id}/documents/{document_id}`
- `DELETE /api/platform/knowledge-bases/{kb_id}/documents/{document_id}`

Phase 3.3 仍不做解析、切块、embedding、索引和 search。先把文档 metadata、owner-private 访问控制、文件安全边界和 audit 设计清楚。

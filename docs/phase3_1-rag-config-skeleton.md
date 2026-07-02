# Phase 3.1：RAG Config Skeleton，默认关闭

## 1. 本阶段目标

Phase 3.1 在 Phase 3.0 已完成 AgentScope RAG Service 架构对齐之后，只实现最小 RAG 配置骨架、配置状态解析和安全能力展示。

本阶段只做：

- 增加 RAG 配置项。
- 增加 RAG 配置状态对象和 resolver。
- 保持真实 RAG runtime 默认关闭。
- 通过现有 `GET /api/platform/overview` 展示 RAG 配置状态。
- 增加离线、无网络、不会污染真实配置的 smoke test。
- 为 Phase 3.2 KnowledgeBase Facade Skeleton 做准备。

本阶段不实现 KnowledgeBase CRUD、Document 上传、解析、切块、Embedding、索引、RAG search、Agent-KB binding、Chat RAG integration、RAG runtime tool、Qdrant 部署、BlobStore 接入或 index worker。

## 2. 当前配置项

`.env.example` 新增：

```env
# Phase 3.1 RAG config skeleton.
# RAG runtime remains disabled by default.
PLATFORM_ENABLE_RAG=false
PLATFORM_RAG_MODE=disabled
PLATFORM_RAG_NATIVE_BASE_URL=
PLATFORM_RAG_ISOLATION_STRATEGY=collection_per_kb
PLATFORM_RAG_ENABLE_INDEX_WORKER=false
```

默认值全部保持安全关闭。

## 3. 配置项含义

| 配置 | 含义 |
| --- | --- |
| `PLATFORM_ENABLE_RAG` | 是否请求启用 RAG。默认 `false`。Phase 3.1 中即使为 `true`，也不能真正启用 RAG runtime。 |
| `PLATFORM_RAG_MODE` | RAG 模式。允许值只有 `disabled` 和 `native_service`。 |
| `PLATFORM_RAG_NATIVE_BASE_URL` | 未来 AgentScope RAG Service 的基础地址。Phase 3.1 不连接该地址，overview 也不会返回完整地址。 |
| `PLATFORM_RAG_ISOLATION_STRATEGY` | 隔离策略。允许值为 `collection_per_kb` 和 `shared_collection_metadata_filter`。 |
| `PLATFORM_RAG_ENABLE_INDEX_WORKER` | 是否请求启用 index worker。Phase 3.1 明确拒绝任何 `true` 请求，状态必须为 `misconfigured`。 |

`PLATFORM_RAG_MODE` 说明：

- `disabled`：RAG 未配置或关闭。
- `native_service`：未来计划连接 AgentScope RAG Service。

不要在 Phase 3.1 增加 `local_qdrant`、`production`、`local` 等尚未实现的模式。

## 4. requested_enabled 和 effective_enabled

`requested_enabled` 表示配置层是否请求启用 RAG，对应 `PLATFORM_ENABLE_RAG`。

`effective_enabled` 表示真实 RAG runtime 是否已经启用。Phase 3.1 必须始终为 `false`。

因此即使配置如下：

```env
PLATFORM_ENABLE_RAG=true
PLATFORM_RAG_MODE=native_service
PLATFORM_RAG_NATIVE_BASE_URL=http://rag-service.invalid
```

也只代表“配置请求已被识别”，不代表真实 RAG 已经启用。

## 5. 为什么 enable=true 也不启用 RAG

Phase 3.1 的目标是配置骨架，不是 RAG runtime 接入。真实接入至少需要：

- `KnowledgeBaseManager`
- parser / chunker
- BlobStore
- VectorStore
- index worker
- KnowledgeBase facade
- Document metadata
- RAG permission 和 audit

这些能力未完成前，直接启用 RAG 会绕过平台多租户隔离、权限和审计边界。所以 Phase 3.1 强制：

```text
effective_enabled = false
runtime_registered = false
```

## 6. 状态说明

`backend/app/rag/config.py` 提供：

```python
resolve_rag_config_status(settings)
build_rag_service_plan(settings)
```

`build_rag_service_plan` 是兼容现有 capability 展示的 wrapper，内部调用 `resolve_rag_config_status`。

状态对象字段：

- `requested_enabled`
- `effective_enabled`
- `mode`
- `native_base_url_configured`
- `isolation_strategy`
- `index_worker_requested`
- `runtime_registered`
- `status`
- `issues`

兼容字段：

- `enabled`
- `mode_valid`
- `isolation_strategy_valid`
- `index_worker_enabled`
- `knowledge_base_manager_enabled`
- `blob_store_enabled`
- `vector_store_enabled`
- `notes`

状态值：

| 状态 | 条件 | 结果 |
| --- | --- | --- |
| `disabled` | `PLATFORM_ENABLE_RAG=false` | RAG 关闭，`effective_enabled=false`，`runtime_registered=false`。 |
| `configured_not_implemented` | `enable=true`、`mode=native_service`、base URL 已配置、隔离策略合法、未请求 index worker | 配置被识别，但真实 RAG runtime 尚未实现。 |
| `misconfigured` | mode 非法、enable=true 但 mode=disabled、enable=true 且 base URL 为空、隔离策略非法、请求 index worker | 配置有问题，fail closed。 |

固定规则：

```text
PLATFORM_RAG_ENABLE_INDEX_WORKER=true
-> status=misconfigured
-> effective_enabled=false
-> runtime_registered=false
```

后续 Phase 3 真正接入 worker 时再调整该规则。

配置错误只写入 `issues`，不会抛未捕获异常，不影响 AgentScope 主链路启动。

## 7. Overview 展示字段

`GET /api/platform/overview` 的 `phase` 更新为：

```text
phase-3.1
```

`features` 中新增扁平字段：

```json
{
  "rag_config_skeleton": true,
  "rag_requested_enabled": false,
  "rag_effective_enabled": false,
  "rag_mode": "disabled",
  "rag_native_base_url_configured": false,
  "rag_runtime_registered": false,
  "rag_isolation_strategy": "collection_per_kb",
  "rag_index_worker_requested": false,
  "rag_status": "disabled",
  "rag_issues": []
}
```

同时保留 `features.rag` 对象用于查看完整安全状态。

安全要求：

- 不返回完整 `PLATFORM_RAG_NATIVE_BASE_URL`。
- 不返回任何 API Key。
- 不返回文档内容。
- 不删除已有 Tool、Workspace、Permission、Audit 字段。

## 8. 安全边界

配置状态解析必须满足：

- 不访问网络。
- 不连接 AgentScope RAG Service。
- 不调用 AgentScope 原生 `/knowledge_bases`。
- 不实例化 `KnowledgeBaseManager`。
- 不实例化 `QdrantStore`。
- 不实例化 BlobStore。
- 不启动 index worker。
- 不读取文档。
- 不创建向量 collection。
- 不注册 `/api/platform/knowledge-bases`。
- 不修改 workspace、permission 文件或 audit 文件。
- 不记录完整 base URL。
- 不记录任何密钥。

## 9. 默认关闭策略

默认配置：

```env
PLATFORM_ENABLE_RAG=false
PLATFORM_RAG_MODE=disabled
PLATFORM_RAG_NATIVE_BASE_URL=
PLATFORM_RAG_ISOLATION_STRATEGY=collection_per_kb
PLATFORM_RAG_ENABLE_INDEX_WORKER=false
```

默认结果：

```text
requested_enabled=false
effective_enabled=false
runtime_registered=false
status=disabled
issues=()
```

## 10. 本地 smoke test

语法检查：

```powershell
python -m compileall backend/app
python -m compileall scripts
```

离线 smoke test：

```powershell
python scripts/smoke_phase3_1_rag_config.py
```

脚本覆盖：

- 默认配置。
- 请求启用 `native_service` 且配置完整。
- `enable=true` 但 base URL 缺失。
- 非法 mode。
- 非法 isolation strategy。
- 请求启用 index worker。
- 安全检查：不泄露完整 native base URL、不包含 API Key、不包含文档内容、不创建真实 RAG runtime。

成功输出：

```text
Phase 3.1 RAG config skeleton smoke passed.
```

## 11. ECS smoke test 设计

本阶段 Codex 不操作 ECS。同步代码后，在 ECS 上执行：

```bash
cd /app/agent-platform
git pull
python -m compileall backend/app
python -m compileall scripts
python scripts/smoke_phase3_1_rag_config.py
```

重启 8891 前保持：

```bash
export PLATFORM_ENABLE_RAG=false
export PLATFORM_RAG_MODE=disabled
export PLATFORM_RAG_NATIVE_BASE_URL=
export PLATFORM_RAG_ISOLATION_STRATEGY=collection_per_kb
export PLATFORM_RAG_ENABLE_INDEX_WORKER=false
```

验证：

```bash
curl -s http://127.0.0.1:8891/platform/health | python -m json.tool
```

```bash
curl -s \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  http://127.0.0.1:8891/api/platform/overview \
  | python -m json.tool
```

预期：

- `phase=phase-3.1`
- `rag_config_skeleton=true`
- `rag_requested_enabled=false`
- `rag_effective_enabled=false`
- `rag_mode=disabled`
- `rag_runtime_registered=false`
- `rag_status=disabled`
- 原有 Phase 1 和 Phase 2 features 仍存在

确认没有新增平台 KB 路由：

```bash
curl -s http://127.0.0.1:8891/openapi.json \
  | python -c "import sys,json; d=json.load(sys.stdin); print([p for p in d.get('paths', {}) if 'knowledge-bases' in p or 'knowledge_bases' in p])"
```

预期不出现：

```text
/api/platform/knowledge-bases
```

## 12. 当前限制

- RAG 仍不可用。
- 不提供 KnowledgeBase CRUD。
- 不提供 Document 上传。
- 不提供 RAG search。
- 不接 embedding。
- 不部署 Qdrant。
- 不启用 BlobStore。
- 不启用 index worker。
- 不做 Agent-KB binding。
- 不做 Chat RAG integration。

## 13. Phase 3.2 建议

建议 Phase 3.2 做 KnowledgeBase Facade Skeleton：

- 新增 `/api/platform/knowledge-bases` 路由 skeleton。
- 定义 KB schema 和 metadata 字段。
- 继续默认关闭真实 RAG runtime。
- 不上传文档。
- 不 search。
- 不调用 embedding。
- 所有接口继续使用 `X-Tenant-ID` / `X-User-ID`。

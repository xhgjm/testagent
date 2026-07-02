# RAG 模块说明

`backend/app/rag` 是 Phase 3 RAG Service 平台封装的预留目录。

当前状态：Phase 3.0 只完成 AgentScope RAG 能力核验和架构对齐设计，没有启用真实 RAG runtime，没有新增 RAG API，也没有连接 Qdrant、embedding、BlobStore 或 index worker。

## 已有文件

- `config.py`：返回 `RagServicePlan(enabled=False, ...)`，用于 `/api/platform/capabilities` 展示 RAG 规划状态。

## 后续建议模块

Phase 3.1+ 可以按小步增加：

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
- 不实现 RAG upload/search/chat integration。
- 不把 RAG 直接做成 runtime tool。
- 不改变 Phase 1 / 1.5 / 2 的现有接口。

详细设计见：

- `docs/phase3_0-rag-service-architecture-alignment.md`

# Roadmap

## Phase 0: Environment And Scaffold

- 创建独立 `agent-platform` 项目。
- 建立 backend / frontend / deploy / docs 结构。
- 配置 `.env.example`、`.gitignore`、README。
- 后端 FastAPI scaffold 可启动。
- 预留 AgentScope Agent Service 接入点。

## Phase 1: Agent Service Main Chain

- 确认 AgentScope 2.0.3 Agent Service import 路径。
- 接入 User、Credential、Agent、Workspace、Session、Schedule、MessageBus。
- 跑通 Credential -> Agent -> Session -> Chat -> SSE -> Message History。
- 验证 userA / userB 隔离。

## Phase 2: Workspace + Tool + Permission

- 接入 LocalWorkspaceManager。
- 引入 DockerWorkspaceManager 或 E2B Workspace。
- 实现 extra_agent_tools 工厂。
- 实现工具权限校验和审计。
- 加入预算控制和 tracing middleware。

## Phase 3: RAG Service

- 接入 KnowledgeBase 和 Document API。
- 接入 QdrantStore。
- 接入 LocalBlobStore，后续支持 OSS / S3 / MinIO。
- 接入 Parser、Chunker、异步 Index worker。
- 提供 tenant-aware RAG retrieval tool。

## Phase 4: Long-term Memory

- 默认关闭长期记忆。
- 按 Agent 策略开启 static_control / agent_control。
- 增加敏感信息过滤。
- 增加记忆删除、导出和审计。

## Phase 5: Agent Team

- 接入 Agent Team。
- 支持 Leader Session 派生 Worker Session。
- 注册 explorer / coder / tester / reviewer 等 SubAgentTemplate。
- 增加 team event tracing 和 worker session history。

## Phase 6: Enterprise Auth, Audit, And Ops

- 替换 `X-User-ID` 为 JWT / OAuth / 企业统一登录。
- 引入 RBAC / ABAC。
- 完善审计日志、限流、预算、指标和告警。
- 完善 systemd、Docker Compose、CI/CD。

## Phase 7: HiMarket / API Gateway

- 将 HiMarket 作为 API Gateway / 应用市场方向接入。
- 对外发布企业 Agent 应用。
- 增加应用授权、订阅、调用统计和计费。

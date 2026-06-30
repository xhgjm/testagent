# Demo Script

## 1. Opening

本项目不是单体 RAG 问答机器人，而是基于 AgentScope 2.0.3 Agent Service 的企业级多租户 Agent 平台底座。

核心目标是支持多租户、多用户、多 Agent、多 Session，并为 Credential、Workspace、Tool、Permission、Middleware、RAG、Memory、Agent Team 预留企业级扩展能力。

## 2. Architecture

打开 `docs/architecture.md`，展示 Mermaid 架构图。

强调：

- Agent 是模板。
- Session 是运行状态。
- Tenant / User / Agent / Session 是平台隔离主线。
- RAG、Memory、Team 是平台能力，不是项目命名和唯一目标。

## 3. ECS Deployment

展示 ECS 环境：

```bash
cat /etc/os-release
python --version
git --version
redis-cli ping
```

展示部署脚本：

```bash
bash deploy/scripts/check-env.sh
bash deploy/scripts/start-backend.sh
```

## 4. Open API Docs

打开：

```text
http://ECS-IP:8891/docs
```

展示：

- `/health`
- `/api/me`
- `/api/platform/capabilities`

## 5. userA Flow

使用 userA 模拟身份：

```bash
curl -H "X-User-ID: userA" -H "X-Tenant-ID: tenantA" http://ECS-IP:8891/api/me
```

后续 Phase 1 演示：

- userA 创建 Credential
- userA 创建 Agent
- userA 创建 Session
- userA 发起 Chat
- userA 订阅 SSE
- userA 查询 Message History

## 6. userB Isolation

使用 userB 模拟身份：

```bash
curl -H "X-User-ID: userB" -H "X-Tenant-ID: tenantA" http://ECS-IP:8891/api/me
```

说明后续验证：

- userB 不能看到 userA 的 Credential。
- userB 不能看到 userA 的 Session。
- userB 的 Workspace 路径与 userA 隔离。

## 7. SSE / Message

第一阶段 scaffold 说明 SSE / Message 为 TODO。

后续接入 AgentScope MessageBus 后演示：

- Chat 过程中实时输出 Event。
- 完成后查询 Message History。
- Event 和 Message 记录 tenant_id、user_id、agent_id、session_id。

## 8. Expansion Plan

展示以下扩展规划：

- Workspace：Local -> Docker / E2B
- Permission：工具调用前鉴权，调用后审计
- RAG：KnowledgeBase、Qdrant、BlobStore、Index worker
- Memory：默认关闭，按 Agent 策略开启
- Team：Leader Session 派生 Worker Session
- HiMarket：后续作为 API Gateway / 应用市场接入

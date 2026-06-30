# Phase 1 Smoke Test

本文档用于验证 AgentScope 2.0.3 Agent Service 已经作为 `agent-platform` 后端入口接入。

## 1. Redis

确认 Redis 可连接：

```bash
redis-cli -h "${REDIS_HOST:-127.0.0.1}" -p "${REDIS_PORT:-6379}" ping
```

期望输出：

```text
PONG
```

## 2. Environment

确认 `.env` 存在并包含关键变量：

```bash
test -f .env
grep -E "^(AGENT_SERVICE_HOST|AGENT_SERVICE_PORT|REDIS_HOST|REDIS_PORT|REDIS_DB|WORKSPACE_BASEDIR|WORKSPACE_TTL_SECONDS)=" .env
```

## 3. Start Backend

本地开发：

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8891 --reload
```

ECS：

```bash
bash deploy/scripts/check-env.sh
bash deploy/scripts/start-backend.sh
```

## 4. OpenAPI Docs

打开：

```text
http://127.0.0.1:8891/docs
```

在 ECS 上：

```text
http://ECS-IP:8891/docs
```

期望看到 AgentScope Agent Service 原生接口，以及平台自定义接口。

## 5. Platform Health

```bash
curl http://127.0.0.1:8891/platform/health
```

期望包含：

```json
{
  "status": "ok",
  "agent_service": "agentscope"
}
```

## 6. Current User

```bash
curl -H "X-User-ID: userA" -H "X-Tenant-ID: tenantA" http://127.0.0.1:8891/api/me
```

期望返回：

```json
{
  "tenant_id": "tenantA",
  "user_id": "userA",
  "role": "user",
  "permissions": []
}
```

## 7. Platform Capabilities

```bash
curl -H "X-User-ID: userA" -H "X-Tenant-ID: tenantA" http://127.0.0.1:8891/api/platform/capabilities
```

期望看到：

- `agentscope_agent_service=enabled`
- `storage=RedisStorage`
- `message_bus=RedisMessageBus`
- workspace path includes tenant / user isolation plan
- RAG / Memory / Team are present as disabled or planned capabilities

## 8. Create Credential

Credential API 来自 AgentScope Agent Service 原生接口。请以 `/docs` 中展示的实际路径和 schema 为准。

建议验证流程：

1. 在 `/docs` 中找到 Credential create 接口。
2. 使用 `X-User-ID: userA` 和 `X-Tenant-ID: tenantA`。
3. 创建一个不包含真实生产密钥的测试 Credential。
4. 确认 userA 可以读取。
5. 切换 `X-User-ID: userB`，验证隔离策略。

示例占位：

```bash
curl -X POST http://127.0.0.1:8891/<CREDENTIAL_CREATE_PATH_FROM_DOCS> \
  -H "Content-Type: application/json" \
  -H "X-User-ID: userA" \
  -H "X-Tenant-ID: tenantA" \
  -d '<REQUEST_BODY_FROM_DOCS>'
```

## 9. Create Agent

Agent API 来自 AgentScope Agent Service 原生接口。请以 `/docs` 中展示的实际路径和 schema 为准。

建议验证：

1. 创建 Agent 模板。
2. 绑定测试 Credential。
3. 确认 Agent 是模板，不直接代表运行状态。

示例占位：

```bash
curl -X POST http://127.0.0.1:8891/<AGENT_CREATE_PATH_FROM_DOCS> \
  -H "Content-Type: application/json" \
  -H "X-User-ID: userA" \
  -H "X-Tenant-ID: tenantA" \
  -d '<REQUEST_BODY_FROM_DOCS>'
```

## 10. Create Session

Session API 来自 AgentScope Agent Service 原生接口。请以 `/docs` 中展示的实际路径和 schema 为准。

建议验证：

1. 使用已创建的 Agent 创建 Session。
2. 记录 `session_id`。
3. 确认 Session 是运行状态。

示例占位：

```bash
curl -X POST http://127.0.0.1:8891/<SESSION_CREATE_PATH_FROM_DOCS> \
  -H "Content-Type: application/json" \
  -H "X-User-ID: userA" \
  -H "X-Tenant-ID: tenantA" \
  -d '<REQUEST_BODY_FROM_DOCS>'
```

## 11. Chat

Chat API 来自 AgentScope Agent Service 原生接口。请以 `/docs` 中展示的实际路径和 schema 为准。

如果 AgentScope 当前 OpenAPI 显示 `POST /chat`，可按文档 schema 发送请求。

示例占位：

```bash
curl -X POST http://127.0.0.1:8891/<CHAT_PATH_FROM_DOCS> \
  -H "Content-Type: application/json" \
  -H "X-User-ID: userA" \
  -H "X-Tenant-ID: tenantA" \
  -d '<REQUEST_BODY_FROM_DOCS>'
```

## 12. SSE Stream

按用户确认的 AgentScope Agent Service 约定，验证：

```text
/sessions/{session_id}/stream
```

示例：

```bash
curl -N -H "X-User-ID: userA" -H "X-Tenant-ID: tenantA" http://127.0.0.1:8891/sessions/<SESSION_ID>/stream
```

期望看到 SSE event stream。

## 13. Message History

按用户确认的 AgentScope Agent Service 约定，验证：

```text
/sessions/{session_id}/messages
```

示例：

```bash
curl -H "X-User-ID: userA" -H "X-Tenant-ID: tenantA" http://127.0.0.1:8891/sessions/<SESSION_ID>/messages
```

期望返回该 Session 的消息历史。

## 14. Isolation Checks

使用 userA：

```bash
curl -H "X-User-ID: userA" -H "X-Tenant-ID: tenantA" http://127.0.0.1:8891/api/platform/capabilities
```

使用 userB：

```bash
curl -H "X-User-ID: userB" -H "X-Tenant-ID: tenantA" http://127.0.0.1:8891/api/platform/capabilities
```

期望 workspace plan 中 user_id 不同。后续在真实 Credential / Agent / Session 存储接入后，还需要验证资源查询隔离。

ECS 演示环境统一使用 `8891`，因为 `8000` 已被已有服务占用。本地开发如果 `8000` 没被占用，可以在 `.env` 或启动命令中自行改回 `8000`。

## 15. Troubleshooting

### `TypeError: 'list' object is not callable`

如果 ECS 日志在 `agentscope/app/_service/_chat.py` 的 `ChatService.run` 中出现：

```text
TypeError: 'list' object is not callable
```

说明传给 AgentScope `create_app` 的 `extra_agent_tools` 或 `extra_agent_middlewares` 被误传成了列表，例如 `[]`。AgentScope 2.0.3 会在运行时调用它们，因此必须传入 async factory：

```python
async def build_extra_agent_tools(user_id: str, agent_id: str, session_id: str) -> list:
    return []

async def build_extra_agent_middlewares(user_id: str, agent_id: str, session_id: str) -> list:
    return []
```

`create_app` 中应传函数本身：

```python
extra_agent_tools=build_extra_agent_tools
extra_agent_middlewares=build_extra_agent_middlewares
```

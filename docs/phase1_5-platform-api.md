# Phase 1.5 Platform API Facade

Phase 1.5 目标是在 AgentScope 2.0.3 Agent Service 之上封装企业平台 API facade，并开始实现基础多租户隔离。

本阶段仍然保留 AgentScope 原生接口，用于底层调试；企业用户推荐调用 `/api/platform/...`。

## Why Platform API Facade

AgentScope 原生接口适合作为底层 Agent Service 能力，但企业平台入口需要：

- 简化请求体。
- 隐藏底层实现细节。
- 统一租户和用户隔离策略。
- 避免企业用户直接依赖 AgentScope 原生 schema。
- 为 Workspace、Tool、Permission、RAG、Memory、Agent Team 提供稳定的平台入口。

## Why Not Expose Native APIs As Enterprise APIs

直接暴露原生接口会带来几个问题：

- 企业租户隔离逻辑分散在调用方。
- 后续平台治理、审计、权限、预算控制难以统一。
- AgentScope 原生 schema 变化会直接影响企业用户。
- API Key 等敏感信息更容易被误返回或误记录。

因此，AgentScope 原生接口保留为底层调试面，企业入口统一走平台 facade。

## Scoped Isolation

外部请求继续使用：

```text
X-Tenant-ID: tenantA
X-User-ID: userA
```

平台内部调用 AgentScope 原生接口时使用：

```text
X-User-ID: tenantA:userA
```

即：

```python
scoped_user_id = f"{tenant_id}:{user_id}"
```

这样 `tenantA:userA` 和 `tenantB:userA` 在 AgentScope 底层会被视为不同用户，从而实现基础多租户隔离。

平台响应默认不暴露 `scoped_user_id`。如需调试，可在开发环境中临时增加 debug 字段，但不能作为生产响应契约。

## API List

- `GET /api/platform/overview`
- `POST /api/platform/credentials`
- `POST /api/platform/agents`
- `GET /api/platform/agents`
- `POST /api/platform/sessions`
- `GET /api/platform/sessions?agent_id=...`
- `POST /api/platform/chat`
- `GET /api/platform/sessions/{session_id}/messages?agent_id=...`
- `GET /api/platform/sessions/{session_id}/stream-url?agent_id=...`

AgentScope 原生接口仍然保留，例如 `/credential/`、`/agent/`、`/sessions/`、`/chat/`、`/sessions/{session_id}/messages`。

## Smoke Test

以下命令假设后端运行在 `127.0.0.1:8891`。

### 1. Health

```bash
curl -s http://127.0.0.1:8891/platform/health | python -m json.tool
```

### 2. Overview

```bash
curl -s \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  http://127.0.0.1:8891/api/platform/overview \
  | python -m json.tool
```

### 3. Create Credential

API Key 使用环境变量，不要写死在命令里。

```bash
read -s -p "Enter API KEY: " LLM_API_KEY
echo
export LLM_API_KEY
export BASE_URL="https://api.deepseek.com"

python - <<'PY'
import os, json
body = {
    "provider": "openai_compatible",
    "name": "DeepSeek V4 Flash",
    "api_key": os.environ["LLM_API_KEY"],
    "base_url": os.environ["BASE_URL"]
}
open("/tmp/platform_credential_body.json", "w", encoding="utf-8").write(json.dumps(body, ensure_ascii=False))
PY

curl -s -X POST "http://127.0.0.1:8891/api/platform/credentials" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  --data-binary "@/tmp/platform_credential_body.json" \
  | tee /tmp/platform_credential.json | python -m json.tool
```

提取 `CREDENTIAL_ID`：

```bash
export CREDENTIAL_ID=$(python - <<'PY'
import json
d = json.load(open("/tmp/platform_credential.json"))
print(d.get("credential_id") or d.get("id") or d.get("data", {}).get("credential_id") or d.get("data", {}).get("id"))
PY
)

echo "CREDENTIAL_ID=$CREDENTIAL_ID"
```

### 4. Create Agent

```bash
python - <<'PY'
import json
body = {
    "name": "Enterprise Platform Test Agent",
    "system_prompt": "你是企业平台测试 Agent。"
}
open("/tmp/platform_agent_body.json", "w", encoding="utf-8").write(json.dumps(body, ensure_ascii=False))
PY

curl -s -X POST "http://127.0.0.1:8891/api/platform/agents" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  --data-binary "@/tmp/platform_agent_body.json" \
  | tee /tmp/platform_agent.json | python -m json.tool
```

提取 `AGENT_ID`：

```bash
export AGENT_ID=$(python - <<'PY'
import json
d = json.load(open("/tmp/platform_agent.json"))
print(d.get("agent_id") or d.get("id") or d.get("data", {}).get("agent_id") or d.get("data", {}).get("id"))
PY
)

echo "AGENT_ID=$AGENT_ID"
```

### 5. Create Session

```bash
export MODEL_NAME="deepseek-v4-flash"

python - <<'PY'
import os, json
body = {
    "agent_id": os.environ["AGENT_ID"],
    "credential_id": os.environ["CREDENTIAL_ID"],
    "name": "tenantA userA platform test session",
    "model": os.environ.get("MODEL_NAME", "deepseek-v4-flash"),
    "model_type": "openai_chat_model",
    "temperature": 0.3
}
open("/tmp/platform_session_body.json", "w", encoding="utf-8").write(json.dumps(body, ensure_ascii=False))
PY

curl -s -X POST "http://127.0.0.1:8891/api/platform/sessions" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  --data-binary "@/tmp/platform_session_body.json" \
  | tee /tmp/platform_session.json | python -m json.tool
```

提取 `SESSION_ID`：

```bash
export SESSION_ID=$(python - <<'PY'
import json
d = json.load(open("/tmp/platform_session.json"))
print(d.get("session_id") or d.get("id") or d.get("data", {}).get("session_id") or d.get("data", {}).get("id"))
PY
)

echo "SESSION_ID=$SESSION_ID"
```

### 6. Get Stream URL

```bash
curl -s \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  "http://127.0.0.1:8891/api/platform/sessions/${SESSION_ID}/stream-url?agent_id=${AGENT_ID}" \
  | python -m json.tool
```

### 7. Open SSE In Terminal A

```bash
curl -N \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  "http://127.0.0.1:8891/sessions/${SESSION_ID}/stream?agent_id=${AGENT_ID}"
```

SSE 暂时仍使用 AgentScope 原生 endpoint。后续阶段再实现平台 SSE proxy。

### 8. Post Chat In Terminal B

```bash
python - <<'PY'
import os, json
body = {
    "agent_id": os.environ["AGENT_ID"],
    "session_id": os.environ["SESSION_ID"],
    "message": "你好，请只回复一句：Agent 平台测试成功。"
}
open("/tmp/platform_chat_body.json", "w", encoding="utf-8").write(json.dumps(body, ensure_ascii=False))
PY

curl -s -X POST "http://127.0.0.1:8891/api/platform/chat" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  --data-binary "@/tmp/platform_chat_body.json" \
  | python -m json.tool
```

### 9. Get Messages

```bash
sleep 8

curl -s \
  -H "X-Tenant-ID: tenantA" \
  -H "X-User-ID: userA" \
  "http://127.0.0.1:8891/api/platform/sessions/${SESSION_ID}/messages?agent_id=${AGENT_ID}" \
  | python -m json.tool
```

### 10. Tenant Isolation Check

创建 `tenantA:userA` 的 Agent 后，使用同一个 user_id 但不同 tenant：

```bash
curl -s \
  -H "X-Tenant-ID: tenantB" \
  -H "X-User-ID: userA" \
  http://127.0.0.1:8891/api/platform/agents \
  | python -m json.tool
```

期望：`tenantB:userA` 看不到 `tenantA:userA` 创建的 Agent。

## Known Limits

- Phase 1.5 只支持 `provider=openai_compatible` 的 Credential facade。
- 目前不实现平台 SSE proxy，只返回原生 stream URL。
- 不实现复杂 RAG。
- 不实现 Long-term Memory。
- 不实现 Agent Team。
- 不引入新数据库，继续复用 AgentScope `RedisStorage` / `RedisMessageBus`。
- 多租户隔离目前基于 `scoped_user_id`，后续还需要 Resource metadata、RBAC / ABAC 和审计增强。

## Phase 2 Preview

Phase 2 建议进入 Workspace + Tool + Permission：

- Workspace 路径和生命周期治理。
- 企业工具注册和挂载。
- Tool permission check。
- Tool audit log。
- Budget / tracing middleware。

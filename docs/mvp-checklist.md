# MVP Checklist

第一阶段验收目标：平台主链路和工程骨架清晰、可启动、可演示、可扩展。

- [x] backend 可以启动。
- [x] `/docs` 可以打开。
- [x] 支持 `X-User-ID` / `X-Tenant-ID`。
- [x] 已接入 AgentScope 2.0.3 `create_app`。
- [x] 已初始化 `RedisStorage`。
- [x] 已初始化 `RedisMessageBus`。
- [x] 已初始化 `LocalWorkspaceManager`。
- [x] 保留平台自定义接口 `/platform/health`、`/api/me`、`/api/platform/capabilities`。
- [ ] 可以创建 Credential。TODO: 通过 AgentScope 原生 API smoke test。
- [ ] 可以创建 Agent。TODO: 通过 AgentScope 原生 API smoke test。
- [ ] 可以创建 Session。TODO: 通过 AgentScope 原生 API smoke test。
- [ ] 可以 `POST /chat`。TODO: 通过 AgentScope 原生 Session chat API smoke test。
- [ ] 可以订阅 SSE。TODO: 验证 `/sessions/{session_id}/stream`。
- [ ] 可以查询 Message。TODO: 验证 `/sessions/{session_id}/messages`。
- [ ] userA / userB 隔离验证。TODO: 接入真实资源存储后验证。
- [ ] Workspace 路径隔离验证。TODO: 当前已有路径规划，待创建真实 Session 后验证。
- [x] README 和部署文档完整。

## Phase 1 Smoke Checks

- `GET /platform/health`
- `GET /api/me`
- `GET /api/platform/capabilities`
- `GET /docs`

示例：

```bash
curl -H "X-User-ID: userA" -H "X-Tenant-ID: tenantA" http://127.0.0.1:8891/api/me
```

更多验证步骤见 [phase1-smoke-test.md](phase1-smoke-test.md)。

ECS 演示环境统一使用 `8891`，因为 `8000` 已被已有服务占用。本地开发如果 `8000` 没被占用，可以在 `.env` 或启动命令中自行改回 `8000`。

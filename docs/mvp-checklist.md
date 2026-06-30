# MVP Checklist

第一阶段验收目标：平台主链路和工程骨架清晰、可启动、可演示、可扩展。

- [x] backend 可以启动。
- [x] `/docs` 可以打开。
- [x] 支持 `X-User-ID`。
- [ ] 可以创建 Credential。TODO: 接入 AgentScope Agent Service Credential API。
- [ ] 可以创建 Agent。TODO: 接入 AgentScope Agent Service Agent 模板 API。
- [ ] 可以创建 Session。TODO: 接入 AgentScope Agent Service Session API。
- [ ] 可以 `POST /chat`。TODO: 接入 Session chat 主链路。
- [ ] 可以订阅 SSE。TODO: 接入 AgentScope MessageBus / Event stream。
- [ ] 可以查询 Message。TODO: 接入 AgentScope Message history。
- [ ] userA / userB 隔离验证。TODO: 接入真实资源存储后验证。
- [ ] Workspace 路径隔离验证。TODO: 当前已有路径规划，待接入 WorkspaceManager 后验证。
- [x] README 和部署文档完整。

## Current Scaffold Checks

- `GET /health`
- `GET /api/me`
- `GET /api/platform/capabilities`

示例：

```bash
curl -H "X-User-ID: userA" -H "X-Tenant-ID: tenantA" http://127.0.0.1:8000/api/me
```

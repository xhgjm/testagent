# 前端说明

第一阶段暂不从零实现复杂前端。MVP 可以先复用 AgentScope `examples/web_ui` 或 AgentScope Studio 能力进行演示，后续再自研企业平台前端。

## 页面规划

1. 登录 / 用户模拟页
2. Credential 管理
3. Agent 管理
4. Session 列表
5. Chat + SSE 页面
6. Message 历史
7. Workspace / Tool / Permission 面板
8. KnowledgeBase 页面
9. Agent Team 页面

## 前端方向

- 当前优先验证后端 Agent Service 主链路和部署流程。
- 自研前端后续可选择 React / Vue / Next.js，但不应阻塞平台底座建设。
- Chat 页面需要支持 SSE event stream、消息历史、用户切换和 session 切换。
- 企业控制台需要按 `tenant_id` / `user_id` 展示资源隔离。
- Phase 3 进入 RAG 后，再规划 KnowledgeBase 管理页面。

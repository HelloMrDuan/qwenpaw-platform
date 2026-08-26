# AgentScope Extension 全量验证摘要

> Strategy note: Telegram and WeCom results below are retained offline
> regression evidence only (`LEGACY / FALLBACK / REFERENCE ONLY`). Production
> uses QwenPaw v2.1.0 built-in Channels. WeChat Customer remains `CUSTOM / TO
> VERIFY`; passing its Mock flow does not authorize deployment.

## 验证范围

本摘要汇总 Phase 9 至 Phase 10 的 Skill、Adapter 与 Plugin 验证证据。验证等级必须区分：

- `REAL_WORKSPACE`：已在真实 AgentScope/QwenPaw Workspace 上传并调用。
- `EXISTING_ADAPTER_OFFLINE`：复用仓库现有生产 Extension Adapter，在 Fake Transport 下完成端到端链路。
- `PLUGIN_CONTRACT_SIMULATION`：Manifest、Plugin Runtime Bridge 和统一契约已验证，但生产消息 Adapter 尚不存在。

## 已验证 Extension

| Extension | 类型 | 验证等级 | Message/Gateway | Response/Receipt | 外部服务 |
| --- | --- | --- | --- | --- | --- |
| `pdf-editor` v1.2.0 | Skill | `REAL_WORKSPACE` | Executor 调用成功 | Artifact 返回成功 | AgentScope Workspace |
| `telegram` | Adapter | `EXISTING_ADAPTER_OFFLINE` | PASS | PASS | 未连接 |
| `wecom` | Plugin + Adapter facade | `EXISTING_ADAPTER_OFFLINE` | PASS | PASS | 未连接 |
| `wechat-customer` | Plugin + Adapter facade | `EXISTING_ADAPTER_OFFLINE` | PASS | PASS | 未连接 |
| `wechat-mp` | Plugin | `PLUGIN_CONTRACT_SIMULATION` | PASS（测试 Facade） | PASS（契约） | 未连接 |
| `hermes` | Plugin | `PLUGIN_CONTRACT_SIMULATION` | PASS（测试 Facade） | PASS（契约） | 未启动 |

## 已验证 Skill

`pdf-editor` 的 Skill Package、Manifest、Executor 和 Artifact 已在真实 AgentScope Workspace 验证。PDF Engine 不属于本阶段改动范围。

## 已验证 Adapter

- Telegram：现有 `TelegramRuntimeAdapter` 完成 Update → MessageEvent → Gateway → Mock Agent → Fake Transport → DeliveryReceipt。
- WeCom：现有 `WeComRuntimeAdapter` 完成 SDK Frame → MessageEvent → Gateway → Mock Agent → Fake Transport → DeliveryReceipt。
- 微信客服：现有 `WeChatCustomerRuntimeAdapter` 完成 post-commit Gateway Event → MessageEvent → Gateway → Mock Agent → Fake Gateway → DeliveryReceipt，并保持 Cursor/DB 归 Gateway 所有。

## 已验证 Plugin

Plugin Runtime Bridge 的静态允许列表覆盖：

- `wecom`
- `wechat-customer`
- `wechat-mp`
- `hermes`

以及 Adapter 类型的 `telegram`。Bridge 只校验 Registry 元数据、历史入口路径、外部探测结果和本地生命周期，不导入或启动历史入口。

微信公众号和 Hermes 当前只达到 Plugin Contract 模拟等级。它们的测试 Facade 不属于生产代码，不能替代未来 Runtime Adapter。

## 统一验证项

四条新增历史 Channel 流程均验证：

1. 输入 fixture 解析；
2. `MessageEvent` 生成；
3. Channel 标识；
4. 用户与 Session 映射；
5. Runtime Gateway 接收；
6. Agent Mock 响应；
7. Response 转换；
8. `DeliveryReceipt`；
9. Trace；
10. Metrics。

历史入口文件在测试前后执行 SHA-256 对比。测试未读取 Secret、未连接 API、未启动 Gateway/Bridge，也未创建真实渠道状态。

## 与真实 Runtime 的边界

```text
Repository Extension
  → Manifest / Registry / Plugin Runtime Bridge
  → Extension Runtime Gateway
  → MessageEvent / DeliveryReceipt / Trace / Metrics
  ║
  ║ 部署与进程边界
  ▼
AgentScope/QwenPaw Runtime
  → Agent 主循环
  → Secret 注入
  → 真实 Gateway/Bridge 进程监管
  → Provider API 与真实投递对账
```

本仓库的 Gateway 是 Extension 层统一调度入口，不替代 AgentScope/QwenPaw Runtime。真实上线前仍需：

- 微信公众号生产 Adapter 与受管 Transport；
- Hermes 生产消息 Transport/调用接口；
- Secret Provider 和网络审批；
- 真实健康探测、限流、重试与 DeliveryReceipt 对账；
- Cloud staging 验收和版本回滚演练。

## 自动测试

```powershell
python -m unittest `
  tests.runtime.test_wecom_agentscope_flow `
  tests.runtime.test_wechat_customer_agentscope_flow `
  tests.runtime.test_wechat_mp_agentscope_flow `
  tests.runtime.test_hermes_agentscope_flow -v

python -m unittest discover -s tests -v
```

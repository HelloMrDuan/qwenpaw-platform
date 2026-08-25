# AgentScope Hermes 模拟链路验证

## 测试目的

验证 `hermes` Plugin 的 Manifest、历史 Gateway 入口、Plugin Runtime Bridge 描述，以及通用消息/响应契约进入 Extension Runtime Gateway 的能力。状态：`PASS_PLUGIN_CONTRACT_SIMULATION`。

Hermes 是外部 Agent/Gateway Plugin，不是单一 Provider Channel Adapter。当前仓库没有面向 Extension Runtime 的 Hermes 消息 Adapter；测试仅使用测试目录内的 Gateway envelope Contract Facade，不导入或执行 Hermes。

## 模拟输入

```json
{
  "message_id": "hermes-flow-1001",
  "user_id": "hermes-offline-user",
  "session_key": "gateway-session-01",
  "timestamp": "2026-08-25T10:15:00Z",
  "text": "你好，Hermes"
}
```

## 转换流程

```text
Hermes gateway-envelope fixture
  → Test-only Hermes Contract Facade
  → MessageEvent(channel=hermes)
  → ExtensionRuntimeGateway.receive_message()
  → Agent Mock
  → Response envelope fixture
  → DeliveryReceipt
```

映射结果：

- 用户：`usr_hermes_hermes-offline-user`
- Session：`ses_hermes_gateway-session-01`
- Conversation：`conv_hermes_gateway-session-01`

## 验证结果

| 验证项 | 结果 |
| --- | --- |
| Manifest 与 `gateway/run.py` 发现 | PASS |
| Plugin Runtime Bridge 允许列表与描述 | PASS |
| 测试 envelope 解析与 MessageEvent | PASS |
| Channel、用户、Session 映射 | PASS |
| Runtime Gateway 接收 | PASS |
| Agent Mock 与 Response envelope | PASS |
| DeliveryReceipt、Trace、Metrics | PASS |
| Hermes 入口未导入且哈希不变 | PASS |

测试入口：`python -m unittest tests.runtime.test_hermes_agentscope_flow -v`。

## 真实接入边界与缺口

本验证未启动 Hermes Gateway、Bridge、Agent Loop 或任何外部服务；未加载其依赖、配置、Session 和 Secret。恢复资产仍缺少与历史版本一致的 Python 安装快照及部分 wrapper。真实接入需要定义受管 Hermes Transport 与 AgentScope Runtime 的职责边界，本阶段不实现。

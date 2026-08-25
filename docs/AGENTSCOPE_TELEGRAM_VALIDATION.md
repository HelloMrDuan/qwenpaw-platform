# AgentScope Telegram 模拟链路验证

## 1. 测试目的

本验证确认已迁移的历史 Telegram Adapter 能够进入仓库内统一 Extension Runtime Gateway 链路，并能将统一响应交回既有 Telegram 出站接口。验证属于本地离线模拟，不代表真实 Telegram Bot 或 AgentScope/QwenPaw Runtime 联调。

验证范围：

- Telegram Update 由 `adapters/telegram/runtime.py` 转换为 `MessageEvent`。
- `ExtensionRuntimeGateway.receive_message("telegram")` 能发现、检查并接收该消息。
- Agent Mock 能消费标准 `MessageEvent` 并返回文本响应。
- 既有 `TelegramRuntimeAdapter.send_response()` 能生成 Telegram `sendMessage` 调用参数和 `DeliveryReceipt`。
- 历史 `telegram_bridge.py` 与 `telegram_bridge_main.py` 在测试前后保持内容哈希不变，且不会被导入或启动。

## 2. 输入模拟消息

既有 Adapter 接受 Telegram Update JSON。Telegram 的 `chat.id`、`from.id`、`message_id` 和 `update_id` 按当前适配器契约使用整数；进入统一消息模型后，渠道标识会规范化为字符串。

```json
{
  "update_id": 90001,
  "message": {
    "message_id": 10001,
    "date": 1700000000,
    "chat": {
      "id": 20001,
      "type": "private"
    },
    "from": {
      "id": 30001,
      "first_name": "测试用户"
    },
    "text": "你好"
  }
}
```

测试不包含 Bot Token、Webhook、网络地址或其他真实凭据。

## 3. 转换流程

```text
Fake Telegram Update
        ↓
TelegramRuntimeAdapter.receive_message()
        ↓
MessageEvent
  channel.type = telegram
  user.id = usr_telegram_30001
  session_id = ses_telegram_20001
        ↓
ExtensionRuntimeGateway.receive_message("telegram")
        ↓
Agent Mock
        ↓
文本 Response
        ↓
TelegramRuntimeAdapter.send_response()
        ↓
Fake Transport: sendMessage(chat_id, text)
        ↓
DeliveryReceipt(status = SENT)
```

Extension Runtime Gateway 负责扩展发现、健康状态、统一消息接收、Trace 与 Metrics；它不执行 AgentScope Agent 主循环。Agent Mock 只用于验证 Gateway 之后的消费边界。

## 4. 验证结果

| 验证项 | 预期结果 | 结果 |
| --- | --- | --- |
| Telegram Update 解析 | 生成标准 `MessageEvent` | PASS |
| Channel 映射 | `channel.type=telegram` | PASS |
| 用户映射 | `usr_telegram_30001` | PASS |
| Session 映射 | `ses_telegram_20001` | PASS |
| 字段完整性 | 版本、消息、Trace、会话、时间、内容、元数据齐全 | PASS |
| Gateway 接收 | 返回 `RECEIVE_MESSAGE` 结果并保留 Trace/Session | PASS |
| Agent Mock | 接收同一 `MessageEvent` 并返回文本 | PASS |
| Telegram 出站转换 | 生成 `sendMessage` 的 `chat_id` 与 `text` 参数 | PASS |
| DeliveryReceipt | 状态为 `SENT`，包含 provider message ID | PASS |
| Observability | Telegram 调用成功次数和接收 Trace 被记录 | PASS |
| 历史 Bridge 隔离 | 未导入、未启动、文件哈希不变 | PASS |

自动验证入口：

```powershell
python -m unittest tests.runtime.test_telegram_agentscope_flow -v
```

## 5. 与真实 Telegram 接入边界

本阶段只验证 Extension 层内的结构转换和调度，不执行以下操作：

- 不连接 Telegram API，不发送真实消息。
- 不读取或注入 `TELEGRAM_BOT_TOKEN`。
- 不启动 `telegram_bridge.py` 或 `telegram_bridge_main.py`。
- 不连接真实 AgentScope/QwenPaw Runtime，不修改其发现或调用机制。
- 不修改 Message Model、历史 Bridge、Agent 主循环或 Telegram 业务逻辑。

Fake Transport 记录的 `method=sendMessage`、`chat_id` 和 `text` 仅代表既有 Adapter 的出站边界。真实环境仍需要由受管进程客户端实现 `TelegramBridgeTransport`，并在部署审批后完成凭据注入、网络连通性和真实 DeliveryReceipt 对账。

# AgentScope WeCom 模拟链路验证

> 战略状态：`LEGACY / FALLBACK / REFERENCE ONLY`。本测试继续保留以保护历史资产和统一消息契约，但不再驱动企业微信自定义 Channel 开发；生产使用 QwenPaw v2.1.0 内置企业微信 Channel。

## 测试目的

验证现有 `WeComRuntimeAdapter` 能将历史企业微信 Bridge 的无凭据消息帧接入 Extension Runtime Gateway，并完成 Mock Agent 响应和统一投递回执。状态：`PASS_EXISTING_ADAPTER_OFFLINE`。

## 模拟输入

```json
{
  "body": {
    "msgid": "wecom-flow-1001",
    "chattype": "group",
    "chatid": "group-flow-01",
    "corpid": "corp-offline",
    "from": {"userid": "user-offline", "name": "离线用户"},
    "text": {"content": "你好，企业微信"}
  }
}
```

输入不包含 `WECOM_BOT_ID`、`WECOM_BOT_SECRET`、`SN_API_KEY` 或真实企业信息。

## 转换流程

```text
Fake WeCom Frame
  → WeComRuntimeAdapter
  → MessageEvent(channel=wecom)
  → ExtensionRuntimeGateway.receive_message()
  → Agent Mock
  → WeComRuntimeAdapter.send_response()
  → Fake Transport
  → DeliveryReceipt
```

映射结果：

- 用户：`usr_wecom_user-offline`
- Session：`ses_wecom_group-flow-01`
- Conversation：`conv_wecom_group-flow-01`
- 回复目标：`group-flow-01`
- 回复关联：`wecom-flow-1001`

## 验证结果

| 验证项 | 结果 |
| --- | --- |
| 输入消息解析与 MessageEvent | PASS |
| Channel、用户、Session 映射 | PASS |
| Runtime Gateway 接收 | PASS |
| Agent Mock 响应 | PASS |
| Response 转换与 DeliveryReceipt | PASS |
| Trace 与 Metrics | PASS |
| 历史 Node Bridge 文件哈希不变 | PASS |

测试入口：`python -m unittest tests.runtime.test_wecom_agentscope_flow -v`。

## 真实接入边界

本验证未启动 `wecom_bridge.mjs` 或 `bot.mjs`，未加载 Node SDK，未连接企业微信 API，也未读取 Secret。生产验收应在 QwenPaw 内置企业微信 Channel 中完成 Bot ID、Secret、扫码授权、媒体目录和群聊上下文验证；不再部署历史 Node Bridge 或实现自定义 `BaseChannel`。

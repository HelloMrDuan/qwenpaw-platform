# AgentScope WeCom 模拟链路验证

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

本验证未启动 `wecom_bridge.mjs` 或 `bot.mjs`，未加载 Node SDK，未连接企业微信 API，也未读取 Secret。真实部署仍需受管 Node 进程、凭据注入、网络检查和真实回执对账；Extension Runtime Gateway 不替代 AgentScope/QwenPaw Runtime。

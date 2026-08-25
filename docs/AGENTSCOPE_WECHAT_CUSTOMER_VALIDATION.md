# AgentScope 微信客服模拟链路验证

## 测试目的

验证现有 `WeChatCustomerRuntimeAdapter` 能在不接触 Gateway 数据库和 Cursor 的情况下，将已持久化的微信客服事件接入 Extension Runtime Gateway。状态：`PASS_EXISTING_ADAPTER_OFFLINE`。

## 模拟输入

```json
{
  "msgid": "customer-flow-1001",
  "msgtype": "text",
  "origin": 3,
  "external_userid": "wm-offline-user",
  "open_kfid": "wk-offline-service",
  "text": {"content": "你好，微信客服"},
  "gateway_delivery": {
    "delivery_id": "gateway-customer-flow-1001",
    "cursor_committed": true,
    "db_claimed": true
  }
}
```

## 转换流程

```text
Fake post-commit Gateway Event
  → WeChatCustomerRuntimeAdapter
  → MessageEvent(channel=wechat-customer)
  → ExtensionRuntimeGateway.receive_message()
  → Agent Mock
  → WeChatCustomerRuntimeAdapter.send_response()
  → Fake Gateway Transport
  → DeliveryReceipt
```

用户与 Session 使用 `sha256(open_kfid + NUL + external_userid)` 的前 24 位映射，避免在内部 Session ID 中暴露客户原始标识。Gateway 始终独占 Cursor、SQLite、去重和真实投递状态。

## 验证结果

| 验证项 | 结果 |
| --- | --- |
| Post-commit 事件解析 | PASS |
| MessageEvent 与稳定 Session 映射 | PASS |
| Cursor 已提交、DB 已认领约束 | PASS |
| Runtime Gateway 接收 | PASS |
| Agent Mock 响应 | PASS |
| Response Facade 与 DeliveryReceipt | PASS |
| Trace 与 Metrics | PASS |
| 历史 Gateway 哈希及状态文件集合不变 | PASS |

测试入口：`python -m unittest tests.runtime.test_wechat_customer_agentscope_flow -v`。

## 真实接入边界

本验证未启动 `wecom_kf_gateway_v345.py`，未访问 8798 端口，未创建或修改数据库，未读取 `CORP_ID`、`APP_SECRET`、`TOKEN`、`AESKEY`、`OPEN_KFID`，也未调用企业微信客服 API。真实部署必须继续由 Gateway 管理 Cursor、Session 数据和重试。

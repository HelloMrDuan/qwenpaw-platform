# AgentScope 微信公众号模拟链路验证

## 测试目的

验证 `wechat-mp` Plugin 的 Manifest、历史入口、Plugin Runtime Bridge 描述、统一消息契约、Runtime Gateway 和投递回执边界。状态：`PASS_PLUGIN_CONTRACT_SIMULATION`。

当前仓库没有生产 `WeChatMpRuntimeAdapter`。测试使用仅位于测试文件中的 decoded-callback Contract Facade；它不会导入历史 Gateway，因此本结果不表示历史签名校验、XML HTTP Handler 或真实回复已接入 Runtime。

## 模拟输入

```json
{
  "MsgId": "mp-flow-1001",
  "CreateTime": 1700000000,
  "FromUserName": "openid-offline-user",
  "ToUserName": "gh-offline-account",
  "MsgType": "text",
  "Content": "你好，微信公众号"
}
```

该对象模拟完成签名校验和 XML 解码后的字段，不包含 `TOKEN`、`signature`、真实 OpenID 或公众号账号。

## 转换流程

```text
Decoded callback fixture
  → Test-only WeChat MP Contract Facade
  → MessageEvent(channel=wechat-mp)
  → ExtensionRuntimeGateway.receive_message()
  → Agent Mock
  → Passive-reply contract fixture
  → DeliveryReceipt
```

用户与 Session 由公众号账号和用户标识的组合哈希生成，隔离不同公众号租户。

## 验证结果

| 验证项 | 结果 |
| --- | --- |
| Manifest 与历史入口发现 | PASS |
| Plugin Runtime Bridge 允许列表与描述 | PASS |
| 测试契约输入解析与 MessageEvent | PASS |
| Channel、用户、Session 映射 | PASS |
| Runtime Gateway 接收 | PASS |
| Agent Mock 与被动回复字段转换 | PASS |
| DeliveryReceipt、Trace、Metrics | PASS |
| 历史 Gateway 未导入且哈希不变 | PASS |

测试入口：`python -m unittest tests.runtime.test_wechat_mp_agentscope_flow -v`。

## 真实接入边界与缺口

- 未运行 `wechat_mp_gateway.py`，未监听 8799。
- 未执行签名校验、XML 网络解析或真实微信回复。
- 未读取 `TOKEN`，未调用微信 API。
- 仍需单独设计生产 Runtime Adapter/受管进程 Transport；本阶段不实现。
- 历史 Gateway 在模块导入时读取 Token，因此离线测试明确禁止导入该文件。

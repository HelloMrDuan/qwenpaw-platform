# WeCom Plugin Runtime Integration

状态：Phase 7.6 历史企业微信Node Bridge外部进程桥接基线。本文描述recovered WeCom Plugin如何进入Extension Runtime，不代表已经连接真实企业微信、Hermes或QwenPaw Runtime。

## 1. 历史资产定位

```text
plugins/wecom/
├── manifest.yaml
└── recovered/
    ├── start_wecom_bridge.sh
    └── wecom-node/
        ├── wecom_bridge.mjs
        ├── bot.mjs
        └── package.json

adapters/wecom/
└── runtime.py
```

Manifest确认WeCom是`plugin`，运行时为`node`，历史入口为：

```text
recovered/wecom-node/wecom_bridge.mjs
```

`adapters/wecom/runtime.py`不是历史Plugin的替代入口，只负责把外部Node进程交付的SDK frame转换为统一消息，并通过Facade回传响应。

## 2. 为什么不能直接加载历史代码

历史Node入口在模块初始化阶段会：

- import未锁定版本的`@wecom/aibot-node-sdk`；
- 读取历史NAS `.env`和企业微信/SenseNova secret；
- 检查Hermes及`sn_agent_runner.py`绝对路径；
- 创建输出目录和日志；
- 构造WebSocket Client并立即`connect()`；
- 注册Hermes、图片生成和Streaming业务处理。

当前仓库缺少dependency lock、真实secret和完整Hermes runner。直接import或启动既不安全也不可复现。因此本阶段把Node Bridge视为外部服务，不执行`.mjs`源码。

## 3. 架构

```text
Extension Registry
    │ loads plugins/wecom/manifest.yaml
    ▼
PluginRuntimeBridge
    │ verifies type=node plugin + recovered entrypoint
    │ receives injected service probe
    ▼
HealthReport + Lifecycle synchronization
    │
    ▼
WeComRuntimeAdapter
    ├── receive_frame() → MessageEvent
    ├── send_response() → DeliveryReceipt
    └── health_check()  → HealthReport
```

外部进程边界：

```text
Recovered WeCom Node process / future supervisor
    │ SDK frame + reply facade + credential-free probe
    ▼
WeComBridgeTransport
    ▼
Extension Runtime
```

测试只使用Fake Transport，不安装Node依赖、不连接WebSocket、不读取secret。

## 4. PluginRuntimeBridge扩展

`core/extensions/runtime/plugin_bridge.py`当前白名单：

| 名称 | 类型 | Runtime | 历史入口 |
| --- | --- | --- | --- |
| `telegram` | adapter | python | `recovered/telegram_bridge_main.py` |
| `wecom` | plugin | node | `recovered/wecom-node/wecom_bridge.mjs` |

WeCom Health流程：

1. Registry验证Manifest；
2. Bridge确认Plugin类型、Node runtime和入口路径；
3. Lifecycle Manager验证本地部署制品；
4. 注入的Probe观察外部服务；
5. 转换为统一`HealthReport`；
6. 同步`INSTALLED/ENABLED/RUNNING/FAILED/DISABLED`状态。

状态规则与Telegram共用：

| 外部状态 | Lifecycle | Health code |
| --- | --- | --- |
| `RUNNING + reachable` | `INSTALLED → ENABLED → RUNNING` | `SERVICE_RUNNING` |
| `STOPPED` | `RUNNING → ENABLED` | `SERVICE_STOPPED` |
| `FAILED` | `FAILED` | `SERVICE_FAILED` |
| `UNKNOWN` | `FAILED` | `SERVICE_UNKNOWN` |
| `RUNNING + unreachable` | `FAILED` | `SERVICE_UNREACHABLE` |

Bridge不执行真实start/stop。Lifecycle变化只同步已观察到的外部状态。

## 5. SDK Frame到MessageEvent

历史`wecom_bridge.mjs`读取的主要字段：

```text
body.msgid
body.chattype
body.chatid              # group
body.from.userid
body.text.content
```

`bot.mjs`还出现`body.content`文本结构，Facade保留该兼容fallback。

映射：

| WeCom frame | MessageEvent |
| --- | --- |
| `body.msgid` | `id`、`trace_id`、`channel.message_id` |
| `body.from.userid` | `user.external_id` |
| `body.from.name/username` | `user.display_name` |
| 群聊`body.chatid` | `channel.thread_id`、session、conversation |
| 单聊sender userid | `channel.thread_id`、session、conversation |
| `body.corpid` | channel/user tenant |
| `body.text.content`/`body.content` | `type=text`、`content.text` |

恢复源码没有稳定读取provider timestamp，因此Adapter使用注入的UTC接收时钟，并明确记录：

```text
metadata.timestamp_source = extension_received_at
```

这避免伪造企业微信原始发送时间。

## 6. Response回传

历史SDK的`replyStream`需要原始frame。统一`MessageEvent`不应保存SDK对象，因此Facade使用：

```text
send_reply(target_id, text, reply_to)
```

- `target_id`：群聊chatid或单聊userid；
- `reply_to`：原始msgid；
- 外部Supervisor负责维护msgid到SDK frame的短期映射；
- Extension层只接收provider message id并生成`DeliveryReceipt`。

本阶段不实现Streaming分段、图片上传或主动消息，这些仍属于历史Bridge/未来正式Adapter的能力边界。

## 7. 保持不变

本阶段未修改：

- `plugins/wecom/recovered/wecom-node/wecom_bridge.mjs`；
- `plugins/wecom/recovered/wecom-node/bot.mjs`；
- Hermes及图片生成逻辑；
- Agent主循环；
- Message Model；
- Streaming核心；
- QwenPaw/AgentScope Runtime；
- Gateway业务逻辑。

专项测试对两份历史`.mjs`记录SHA256，并确认测试前后一致。

## 8. Runtime边界

| Extension层 | WeCom/部署环境 |
| --- | --- |
| Manifest发现与入口身份校验 | Node dependency安装和版本锁 |
| SDK frame到MessageEvent | 企业微信WebSocket连接 |
| Facade响应到DeliveryReceipt | SDK replyStream/send API |
| 注入式Health与Lifecycle同步 | 进程supervisor、PID、端口和重连 |
| Fake Transport离线测试 | Bot ID/secret与Secret Manager |

当前代码不会把WeCom Node Bridge自动接入QwenPaw Runtime，也不会声明企业微信生产连接已经恢复。

## 9. 生产化前置条件

- 恢复并锁定Node版本、SDK版本和lockfile；
- 建立脱敏配置模板及Secret Manager注入；
- 将硬编码NAS路径通过独立wrapper配置化，保留recovered源码基线；
- 实现受监督的Node外部进程与credential-free control API；
- 定义SDK frame缓存、reply_to过期和幂等规则；
- 接入真实Health、重连、指标与告警；
- 定义文本分段、Streaming、媒体与主动发送策略；
- 恢复Hermes runner并完成staging验收；
- 建立升级和回滚演练。

完成这些条件前，Phase 7.6只提供历史企业微信Bridge到Extension Architecture的离线安全桥接。

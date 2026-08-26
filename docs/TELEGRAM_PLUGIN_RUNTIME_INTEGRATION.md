# Telegram Plugin Runtime Integration

> 当前分类：`LEGACY / FALLBACK / REFERENCE ONLY`。生产使用 QwenPaw v2.1.0
> 内置 Telegram Channel；本文不再作为自定义 BaseChannel、Plugin 注册或部署路线。

状态：Phase 7.5 历史 Telegram Bridge 外部进程桥接基线。本文描述 recovered Telegram Adapter 如何进入 Extension Runtime，不代表已经连接真实 Telegram、Hermes 或 QwenPaw Runtime。

## 1. 为什么采用外部进程桥接

当前历史资产：

```text
adapters/telegram/
├── manifest.yaml
├── runtime.py
└── recovered/
    ├── telegram_bridge.py
    ├── telegram_bridge_main.py
    └── start_bridge.sh
```

两份 recovered Python 文件不是可安全 import 的库：

- `telegram_bridge_main.py` 在模块加载阶段创建历史 NAS 状态目录并读取 `.env`；
- `telegram_bridge.py` 在模块加载阶段读取凭证、创建锁并直接进入无限轮询；
- 两者均包含真实 Telegram HTTP 与 Hermes subprocess 路径；
- 历史路径、token、runner、PID和offset运行状态不在当前仓库中。

因此 Extension Runtime 不 import、不patch、不复制这两份实现，而是把历史 Bridge 视为独立外部进程，通过可注入 Facade 观察和转发。

## 2. 当前架构

```text
Extension Registry
    │ loads adapters/telegram/manifest.yaml
    ▼
PluginRuntimeBridge
    │ validates recovered entrypoint identity
    │ receives external service probe
    ▼
Unified HealthReport
    │ synchronizes local Lifecycle state
    ▼
TelegramRuntimeAdapter
    ├── receive_update() → MessageEvent
    ├── send_response()  → DeliveryReceipt
    └── health_check()   → HealthReport
```

历史进程边界：

```text
Recovered Telegram Bridge process
    │ Telegram Update / sendMessage / process probe
    ▼
TelegramBridgeTransport facade
    │ credential-free method boundary
    ▼
Extension Runtime
```

Phase 7.5 测试使用 Fake Transport。没有调用 Telegram API，没有启动 recovered 脚本，也没有执行 Hermes。

## 3. PluginRuntimeBridge

位置：`core/extensions/runtime/plugin_bridge.py`。

Telegram路径的严格白名单：

```text
name:       telegram
type:       adapter
runtime:    python
entrypoint: recovered/telegram_bridge_main.py
```

Phase 7.6起，同一通用Bridge还允许经过独立声明的WeCom Node Plugin；这不会扩大Telegram入口、类型或runtime范围。WeCom规则见`WECOM_PLUGIN_RUNTIME_INTEGRATION.md`。

Bridge 负责：

- 从 Registry 获取已验证的 Manifest metadata；
- 确认类型、runtime、entrypoint和文件路径；
- 先调用 Lifecycle Manager 验证已部署制品；
- 接收外部探针返回的无凭证服务状态；
- 将外部状态转换为统一 `HealthReport`；
- 同步本地生命周期状态。

Bridge 不负责创建进程、读取PID、请求HTTP health endpoint或执行入口。

## 4. 外部服务与生命周期同步

外部探针返回：

- `RUNNING`；
- `STOPPED`；
- `FAILED`；
- `UNKNOWN`；
- `reachable`和安全的detail文本。

同步规则：

| 外部状态 | 本地操作 | 统一Health |
| --- | --- | --- |
| `RUNNING + reachable` | `INSTALLED → ENABLED → RUNNING` | `SERVICE_RUNNING` |
| `STOPPED` | 本地`RUNNING → ENABLED` | `SERVICE_STOPPED` |
| `FAILED` | 写入生命周期`FAILED` | `SERVICE_FAILED` |
| `UNKNOWN` | 写入生命周期`FAILED` | `SERVICE_UNKNOWN` |
| `RUNNING + unreachable` | 写入生命周期`FAILED` | `SERVICE_UNREACHABLE` |
| 本地`DISABLED` | 不探测、不自动启用 | `DISABLED` |
| 部署完整性失败 | 不执行外部探针 | Lifecycle原始错误 |

`runtime_probe_performed=true`只表示注入的探针已运行。探针是否检查PID、端口、HTTP或supervisor状态，由未来部署Provider定义。

## 5. Telegram消息转换

位置：`adapters/telegram/runtime.py`。

输入为历史 Bridge 已使用的 Telegram Update JSON：

```text
update_id
message / edited_message
  ├── message_id
  ├── date
  ├── from.id
  ├── chat.id
  └── text
```

转换为现有 `MessageEvent`，不修改 Message Model：

| Telegram | MessageEvent |
| --- | --- |
| `update_id` | `trace_id`、`metadata.update_id` |
| `message_id` | `channel.message_id` |
| `chat.id` | `channel.thread_id`、`session_id`、`conversation_id` |
| `from.id` | `user.external_id` |
| 姓名/username | `user.display_name` |
| Unix `date` | RFC3339 UTC `timestamp` |
| `text` | `type=text`、`content.text` |

当前历史实现只处理文本，因此非文本Update被明确拒绝。文件、图片、语音下载属于未来Telegram Adapter能力，不能在本阶段伪造。

## 6. Response回传

`send_response(message, response)`：

1. 确认输入是Telegram `MessageEvent`；
2. 从标准metadata/thread引用取得`chat_id`；
3. 通过注入的`TelegramBridgeTransport.send_message`转发纯文本；
4. 返回统一`DeliveryReceipt`。

Runtime Adapter不读取bot token，不自行构造Telegram API URL。真实token只能由未来外部进程Provider或Secret Manager注入。

## 7. 保持不变的历史资产

本阶段未修改：

- `adapters/telegram/recovered/telegram_bridge.py`；
- `adapters/telegram/recovered/telegram_bridge_main.py`；
- Hermes代码和runner；
- Agent主循环；
- Message Model；
- QwenPaw/AgentScope Runtime；
- Gateway业务逻辑。

集成测试会记录两份历史脚本SHA256，并确认执行Bridge测试后哈希保持不变。

## 8. 与QwenPaw Runtime的边界

| Extension层 | QwenPaw/部署环境 |
| --- | --- |
| Registry/Manifest发现 | 真实Extension注册 |
| Update到MessageEvent转换 | Agent任务创建和调度 |
| Response到DeliveryReceipt转换 | 真实Channel发送策略 |
| 注入式外部Health探针 | 进程supervisor、容器和网络 |
| 本地Lifecycle同步 | 生产启停、重启和流量切换 |
| Fake Transport离线测试 | Telegram token与Secret Manager |

当前代码不会把历史Bridge自动接入Runtime，也不会声明Telegram生产服务已恢复。

## 9. 后续生产化门槛

- 为历史进程建立受监督的独立部署单元；
- 用配置模板替换硬编码NAS路径，但必须作为单独迁移，不改原始基线；
- Secret Manager注入token和allowed users；
- PID/HTTP/Telegram `getMe` 分层Health策略；
- polling offset的持久化、备份和幂等恢复；
- MessageEvent到Agent任务的Runtime Provider；
- 超时、重试、限流、分片发送和错误分类；
- staging bot验收及生产回滚方案；
- Hermes runner缺失资产恢复。

这些条件完成前，本阶段仅是历史Bridge与Extension Architecture之间的安全桥接。

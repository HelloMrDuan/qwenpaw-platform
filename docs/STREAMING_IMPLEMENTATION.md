# Extension Streaming Bridge 实施说明

## 1. 当前实现

Phase 4 第一阶段在仓库 Extension 层增加一个同步、离线、内存态 Streaming Bridge，用于证明标准 `StreamEvent` 能够被统一消费和展示层读取。

```text
Skill Executor
    │
    │ SkillResult.events / StreamEvent
    ▼
Extension Streaming Bridge
    ├── publish(event)
    ├── subscribe(StreamConsumer)
    └── replay(session_id)
            │
            ├── StreamCollector / Console prototype
            └── future Runtime or Channel adapter
```

当前 Bridge 提供：

- `StreamingBridge.publish(event)`：验证、存储并同步通知订阅者；
- `StreamingBridge.subscribe(consumer)`：注册实现 `on_event(event)` 的消费者，返回取消订阅函数；
- `StreamingBridge.replay(session_id)`：按发布顺序返回指定 session 的事件；
- `StreamCollector`：离线收集事件，供测试、诊断和展示原型使用；
- `StreamReplay`：验证 sequence、event_id、关联字段、Tool 生命周期和进度单调性。

## 2. PDF Editor 验证链路

PDF Editor 算法和 Engine 没有修改。测试通过现有 Contract Executor 执行一个离线生成 fixture，取得 `SkillResult.events`，逐个发布给 Bridge：

```text
PDF execute
  → tool.start
  → tool.progress × N
  → file.created
  → tool.result
  → StreamingBridge
  → StreamCollector + session replay
```

验收验证事件顺序严格递增、`event_id` 唯一、所有事件属于同一 `session_id`，并确认 Collector 与 replay 得到完全一致的序列。失败路径使用 `tool.error`，错误事件会结束对应 Tool call。

## 3. 与 QwenPaw Runtime Streaming 的边界

| Extension Streaming Bridge | QwenPaw Runtime Streaming |
| --- | --- |
| 当前仓库拥有和测试 | 云端 Runtime 拥有，本仓库不实现 |
| 消费标准 `StreamEvent` | 负责 Agent/模型真实生命周期和流式调度 |
| 单进程、同步、内存 replay | 可采用异步、持久化、消息队列或分布式传输 |
| 不连接真实 Channel | 负责或协调真实 Channel 的发送策略 |
| 不提供 SSE/WebSocket | 可提供面向客户端的网络 Streaming 协议 |
| 不负责模型 token 产生 | 负责将 Agent/模型状态转换为实时事件 |
| 允许 Skill-only 流从 `tool.start` 开始 | 完整 Agent 流通常从 `agent.start` 开始并以 Agent 终态结束 |

Bridge 是 Extension Contract 的参考实现和验证设施，不替代 Runtime event bus，也不推断云端内部实现。

## 4. 当前保证

- 只接受已构造并通过字段校验的 `StreamEvent`；
- 同一 `stream_id` 的 trace、session、conversation 和 task 关联不可变化；
- sequence 必须严格递增；
- `event_id` 在 Bridge 实例内唯一；
- `tool.progress`、`tool.result`、`tool.error` 必须存在前置 `tool.start`；
- progress 百分比不可倒退；
- `file.created` 关联 Tool 时，该 Tool 必须仍在执行；
- Agent 终态后不接受新事件；
- 一个消费者异常不会阻止其他消费者接收，事件在通知前已进入 replay。

## 5. 暂不包含

- QwenPaw Runtime、Agent 或 Channel 修改；
- 真实 Telegram、企业微信或微信客服接入；
- SSE、WebSocket、HTTP endpoint 或消息队列；
- 跨进程持久化、断点续传和分布式幂等；
- 背压、网络重试、Channel 消息更新或分段回复；
- 将 PDF Engine 的 stderr 进度直接接到在线总线。

后续若与 QwenPaw Runtime 对接，应新增独立 Runtime Adapter，将 Runtime 的实际事件入口映射为 `StreamEvent` 并调用 Bridge；不应把网络或云端生命周期逻辑写入 `core/streaming`。

## 6. 离线验证

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests\streaming -p "test_*.py" -v
```

该命令不启动 Runtime，不访问模型服务，也不连接任何真实 Channel。

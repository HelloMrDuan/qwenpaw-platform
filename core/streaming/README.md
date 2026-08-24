# Extension Streaming Bridge

`core/streaming` 是仓库内的离线 Extension 事件桥，不是 QwenPaw Runtime 的事件总线。

它接收已经通过 `core.contracts.StreamEvent` 校验的事件，并提供：

```python
bridge.publish(event)
unsubscribe = bridge.subscribe(consumer)
events = bridge.replay(session_id)
```

主要组件：

- `StreamingBridge`：同步发布、订阅通知和 session replay 入口。
- `StreamReplay`：内存存储及增量顺序、唯一性、关联字段和 Tool 生命周期校验。
- `StreamCollector`：用于测试、诊断和未来 Console 原型的离线消费者。
- `StreamConsumer`：位于 `core/contracts/stream_consumer.py` 的消费接口。

Bridge 支持完整 Agent 流，也支持从 `tool.start` 开始的 Skill-only 流。后者用于消费 PDF Editor 等 Extension Executor 返回的 `SkillResult.events`。

当前实现有意保持同步、单进程和内存态：不包含 SSE/WebSocket、持久化、跨进程消息队列、网络重试、Channel 渲染或 Runtime 生命周期管理。

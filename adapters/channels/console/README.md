# Console Channel Adapter

这是第一个可执行的 Extension `ChannelAdapter`，用于本地 Console 输入/输出和端到端契约验证。它不启动或替代 QwenPaw Runtime。

## 输入

`parse_message()` 接收文本 payload：

```python
{
    "text": "请处理这个任务",
    "user_id": "local-user",
    "session_id": "ses_local",
    "conversation_id": "conv_local"
}
```

输出标准 `MessageEvent`，其中 `channel.type="console"`。未提供的消息、trace、session 和 conversation ID 会生成本地默认值。

## 输出

- `send_message()` 写入完整文本和可选 Artifact 引用；
- `send_stream_event()` 使用 `core.renderers.ConsoleRenderer` 将事件转换为 `RenderedOutput`；
- `ConsoleOutputWriter` 展示实时 delta、状态/Tool 进度、文件 Artifact 和安全错误；
- 每次实际写入返回 `DeliveryReceipt`，无可见输出的事件返回 `None`。

默认输出为 `sys.stdout`。测试可注入 `io.StringIO`，因此不需要网络、凭据、模型或真实 Channel。

## 边界

Adapter 不负责用户输入循环、Agent 调用、Tool 路由、Streaming Bridge 调度、Artifact 下载、Runtime 注册或云端部署。它只实现 Extension Contract 与本地文本流之间的转换。

# Extension Stream Renderers

本目录包含传输无关的离线参考 Renderer。它们把 `StreamEvent` 转换为 `RenderedOutput`，但不会调用 Console、Telegram、企业微信或微信的 SDK/API。

- `ConsoleRenderer`：即时输出文本 delta、安全状态、文件引用和错误。
- `TelegramRenderer`：聚合 delta，并生成“创建消息/节流更新”动作。
- `WeComRenderer`：按字符上限生成分段消息和文件消息动作。
- `WeChatRenderer`：缓冲文本，直到 `flush()` 或终态再生成回复动作。

`RenderedOutput` 只是对未来 Channel Adapter 的建议动作，不是 `DeliveryReceipt`。文件输出仍保留受控 `artifact://` 引用；真实下载链接签发、Provider 上传和发送结果属于 Runtime/Channel Adapter 边界。

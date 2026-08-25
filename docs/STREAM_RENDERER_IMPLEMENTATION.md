# Stream Renderer Extension 实施说明

## 1. 已实现范围

Phase 4.2 在 Extension 层实现了以下内容：

- `core/contracts/stream_renderer.py`
  - `StreamRenderer` Protocol；
  - `RenderedOutput`；
  - `RenderedOutputType`；
  - `render.output.v1` 序列化协议。
- `core/renderers/base.py`
  - sequence、event_id 和流关联校验；
  - `flush()` / `close()` 生命周期；
  - Artifact 与安全错误输出转换。
- `core/renderers/channels.py`
  - `ConsoleRenderer`；
  - `TelegramRenderer`；
  - `WeComRenderer`；
  - `WeChatRenderer`。

这些类是可执行的离线参考策略，不连接任何 Provider。

## 2. Extension 与 Runtime/Channel 边界

| Extension Renderer | QwenPaw Runtime / Channel |
| --- | --- |
| 将 `StreamEvent` 转换为 `RenderedOutput` | 产生真实 Agent/模型事件并调度发送 |
| 描述消息创建、更新、分段和文件交付意图 | 调用 Provider SDK/API |
| 使用内存缓冲和确定性字符阈值 | 处理真实时间节流、限流、重试和持久化 |
| 保留 `artifact://` 引用 | 授权下载、签发短期链接或上传 Provider 文件 |
| 返回展示动作 | 返回真实 `DeliveryReceipt` 和 Provider message ID |
| 离线测试，不需要账号和网络 | 需要测试租户、凭据和 staging 验收 |

Renderer 不替代 Runtime Channel，也不会注册 webhook、轮询消息、发送 Telegram/企业微信/微信消息或读取现有 Channel 配置。

## 3. 推荐的未来对接方式

```text
StreamingBridge
  → Renderer Coordinator
      → renderer.render(event)
      → RenderedOutput[]
          → Channel Adapter
          → DeliveryReceipt
```

未来 Coordinator 应负责：

- 为 session 选择 Renderer 和具体 Channel Adapter；
- 调用 `render()`、定时 `flush()` 并在终态 `close()`；
- 将 `RenderedOutput` 投递给 Channel Adapter；
- 记录 output ID、source event IDs、Provider message ID 和投递状态；
- 将投递失败隔离于 Agent/Skill 结果之外。

该 Coordinator 不在 Phase 4.2 范围内。

## 4. 当前文件事件行为

四个 Renderer 都会把完整 `file.created` Artifact 转为 `RenderedOutput(type="file")`。输出仅包含 Artifact 元数据与交付提示，不解析或暴露物理路径：

- Console：`artifact_reference`；
- Telegram：`attachment_or_link`；
- WeCom：`file_message`；
- WeChat：`download_link`。

实际附件上传或下载链接生成必须在后续受控 Artifact/Channel Adapter 中实现。

## 5. 离线测试

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests\renderers -p "test_*.py" -v
```

测试覆盖：

- StreamEvent 到 RenderedOutput 的转换和序列化；
- Telegram 聚合与消息更新；
- WeCom 分段和余量 flush；
- WeChat 缓冲和终态输出；
- Console 实时 delta；
- 四种文件交付策略；
- sequence、event_id、close 和错误事件。

测试完全离线，不启动 Runtime，不访问模型服务，不连接真实 Channel，也不执行或修改 PDF Editor。

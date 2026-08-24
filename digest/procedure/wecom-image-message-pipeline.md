---
description: wecom-public 返回 image 模式 JSON 后的端到端处理 runbook：U1 生图、逐级压缩 <=1.9MB、media/upload、send_image_message、状态标记、重试与安全回退。
name: 微信图片消息端到端处理流水线
---

# 微信图片消息端到端处理流水线

## 触发条件

wecom-public Agent 返回严格 JSON `{"mode":"image","prompt":"..."}` 时，执行图片生成并发送链路。

## 前置条件

- wecom-public Agent 已运行，模型 `kilo-auto/free`
- `sn_agent_runner.py` 路径可达，SenseNova 环境变量已加载
- 数据库 `generated_images` 表已存在
- 当前会话 `service_state` 为 `0` 或 `1`
- ACK 已在前置步骤中发送给用户

## 步骤

1. **解析 Agent 路由**：从 QwenPaw stdout 提取 `{"mode":"image","prompt":"..."}`，去 SESSION 行与代码块包裹；解析失败则回退普通文本。
2. **生成图片**：直接调用 `sn_agent_runner.py sn-image-generate`，参数 `--prompt <prompt> --image-size 2k --aspect-ratio 1:1 --save-path <unique-output>`；失败则重试最多 2 次，首次失败 `sleep(5)` 秒再试。
3. **压缩适配微信**：调用 `prepare_wecom_image(source_path)` → `upload_path`；保留原图不覆盖。若原图 <=1.9MB 且为 JPG/PNG 则直传；否则 JPEG quality 循环 92→88→82→76→70，每次 `os.path.getsize` 校验；仍超限则逐级缩小分辨率 2048→1800→1600→1400→1200；RGBA/P 转 RGB。
4. **上传 media**：调用 `upload_image_media(upload_path)`，POST `/cgi-bin/media/upload?type=image`，multipart 字段名 `media`，MIME 按扩展名；检查 `errcode==0` 且 `media_id` 非空。
5. **发送图片消息**：调用 `send_image_message(external_userid, media_id)`，POST `/cgi-bin/kf/send_msg`，JSON 含 `msgtype=image`。
6. **状态标记**：仅当最终 `errcode==0` 标记 `completed`；任何关键失败统一标记 `failed`。

## 失败模式与安全约束

- **U1 最终失败**：仅返回固定文本"抱歉，图片生成暂时失败了，请稍后再试。"；禁止泄露 JSON、prompt、stderr、traceback。
- **压缩失败**：返回"🤖 图片已经生成，但处理上传文件时失败了，请稍后再试。"，不调用 media/upload。
- **日志脱敏**：`sanitize_log_text()` 屏蔽 api_key/apikey/token/secret/Authorization/Bearer。
- **数据库**：`generated_images` 记录 msgid/external_userid/open_kfid/prompt/image_path/upload_image_path/media_id/upload_status/send_status/created_at。

## Sources

- wecom-public Agent 的创建与 U1 Fast 生图能力验证（sensenova-u1-fast 模型、34.88s 耗时、2752x1536 PNG 原始输出）见于 [[memory/2026-08-21/tailscale-funnel-and-qwenpaw-setup.md|该会话记录]] 中的 wecom-public Agent 配置与 U1 Fast 图片生成验证段落。
- 这一流水线的完整规范（Agent 路由契约、`prepare_wecom_image` 逐级压缩参数、`upload_image_media` MIME 规则、`generated_images` 表结构及 U1 直接 runner 调用方式）由 [[memory/2026-08-21/wecom-kf-gateway-v34-deployment.md|该 V3.4 部署记录]] 中的核心功能需求章节支持。
- V3.4.3 对 U1 重试机制（最多 2 次、首次失败 sleep 5s）、日志脱敏函数及失败安全回退文本的最终实现，由 [[memory/2026-08-21/wecom-kf-v343-deployment.md|该 V3.4.3 部署记录]] 支持。
- 与此图片流水线共享同一 Gateway 的蓝绿部署与 Funnel 切流约束，见 [[digest/procedure/wecom-gateway-bluegreen-funnel.md|WeCom Gateway 蓝绿部署流程]]。
- 与此流水线相关的企微 API 陷阱（如 service_state 正确 URL、callback 投递不可靠时的 polling 兜底），见 [[digest/wiki/wecom-kf-api-traps-and-workarounds.md|WeCom kf API 已知陷阱]]。

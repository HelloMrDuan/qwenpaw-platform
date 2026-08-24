---
description: 企业微信客服 API 在本次部署中暴露的多个非文档化行为及工程绕过方案
name: WeCom kf API 已知陷阱与绕过方案
---

企业微信客服 API 在本次部署中暴露的多个非文档化行为及工程绕过方案，直接影响 Gateway 的容错逻辑设计。

- **service_state 接口路径错误**：`/cgi-bin/kf/get_service_state` 返回 404，正确端点为 `/cgi-bin/kf/service_state/get`（POST）。生产代码需修正为 POST 携带 `open_kfid` 与 `external_userid`。
- **origin=3 系统消息禁止直接 send_msg**：客户侧系统消息（`origin=3`）触发 95018（session status invalid）。绕过方式：不依赖 `service_state` 前置检查，而是通过 `kf/sync_msg` 拉取真实消息后，仅对文本消息（`msgtype=text`）执行 `send_msg`。
- **callback 投递不可靠**：`kf_msg_or_event` 事件可能不穿透 Funnel，但 `sync_msg` 仍能拉到消息。工程兜底：以 30 秒 daemon thread 轮询 `sync_msg`，cursor 持久化，复用 `processed_messages` 去重，与 callback 共用同一处理入口。
- **DNS 解析失败 ≠ Funnel 故障**：外部 `Could not resolve host` 超时不作为公网失败依据，以本地 healthz 与 Funnel 配置状态为准。

这些先例已沉淀到 [[digest/procedure/wecom-gateway-bluegreen-funnel.md|WeCom Gateway 蓝绿部署与 Funnel 切换流程]] 的失败模式章节，成为后续 Gateway 默认容错逻辑的输入。

## Sources

- 本条目所述的 API 路径修正、95018 根因定位与 callback 穿透失败诊断，由 [[memory/2026-08-21/tailscale-funnel-and-qwenpaw-setup.md|该会话记录]] 中的 V3.2 阻塞分析、V3.3 修复验证及 V3.4.1 回调缺失诊断段落支持。
- 本条目所述的 30 秒 polling 兜底方案、cursor 持久化设计及双实例竞争防护，由 [[memory/2026-08-21/wecom-kf-gateway-v34-deployment.md|该部署记录]] 中的 V3.4.2 工程决策与离线验证段落支持。

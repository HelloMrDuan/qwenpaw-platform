---
description: 微信公众号客服消息接口 48001 api unauthorized 的工程绕过方案：切换为被动回复模式直接返回 XML，并演进至 V2
  直连 QwenPaw HTTP API 网关。
kind: concept
name: WeChat MP 48001 Passive Reply Permission Bypass
---

微信公众号客服消息接口返回 `48001 api unauthorized` 时，可将回调网关切换为**被动回复模式**（直接返回 XML），绕过客服消息 API 的权限限制，无需先在公众平台后台申请接口权限。

- **被动回复原理**：微信服务器在用户消息到达时同步请求回调地址，网关直接构造并返回 XML 响应即可完成回复，全程不调用客服消息 API，因此不受 `48001` 约束。
- **V1 网关**：部署于端口 8799，实现 SHA1 签名验证与被动回复 XML 生成，AI 能力通过调用 `qwenpaw agents chat` 实现（超时 4s）。
- **V2 网关**：进一步直连 QwenPaw HTTP API（端口 8800），为每个微信用户生成独立 `session_id`（`SHA256(user_key)[:24]`），支持 SSE 流式解析与增量文本合并，彻底降低对微信客服接口的依赖。
- **公网暴露**：回调地址通过 Tailscale Funnel 暴露为 `https://qwenpaw-sbs-prod-dj2gm.tail7c303e.ts.net/wechat/mp/callback`，域名不变，仅底层目标端口随版本切换。
- **待办项**：在微信公众平台后台手动启用"客服消息"接口权限，以支持后续主动消息能力。

被动回复模式作为 48001 权限阻塞时的即时回退方案，与 [[digest/wiki/wecom-kf-api-traps-and-workarounds.md|WeCom kf API 已知陷阱与绕过方案]] 中沉淀的企业微信侧 API 路径修正、95018 规避等先例共同构成本项目微信客服 API 的工程绕过知识集。V1/V2 网关的蓝绿并行与 Funnel 切流操作，遵循了 [[digest/procedure/wecom-gateway-bluegreen-funnel.md|WeCom Gateway 蓝绿部署与 Funnel 切换流程]] 中"验收通过才切流、禁止 kill/pkill"的核心约束。公网回调依赖的 Tailscale Funnel 基础设施，其原子迁移与 Background session 管理可参照 [[digest/procedure/tailscale-funnel-foreground-to-background-migration.md|Tailscale Funnel Foreground→Background 原子迁移]] 执行；部署全过程需遵守 [[digest/personal/wecom-production-safety-constraints.md|WeCom 生产环境安全约束集]] 中的安全注入与日志脱敏要求。

## Sources

- 本条目所述的 48001 权限问题诊断、被动回复模式部署、V1/V2 网关架构与 Tailscale Funnel 切换，由 [[memory/2026-08-23/ops-update-20260823.md|该运维更新记录]] 中的"微信公众号回调网关"与"48001 权限问题状态"段落支持。
- 微信公众号 V2 网关所依赖的 Tailscale Funnel Background session 迁移与公网健康验证经验，由 [[memory/2026-08-22.md|该日运维记录]] 中的 Funnel 迁移与 Gateway 状态段落支持。

# Channel 运行现状

## 总览

| Channel | 配置 | 源码 | 启动脚本 | 外部服务 | 当前结论 |
| --- | --- | --- | --- | --- | --- |
| Console | 有，已启用 | 仓库内无运行时源码 | 无独立脚本 | QwenPaw/AgentScope 运行时 | 配置可见，但本机缺少 `qwenpaw` CLI，尚不能启动 |
| Telegram | 有，已禁用 | `channels/` 中无源码；历史记录指向外部 Hermes/插件目录 | 无 | Telegram Bot API、网络/代理、bot token、Hermes/QwenPaw | 只有配置与历史运行证据，不能从仓库独立运行 |
| 企业微信 | 有，已禁用 | `channels/` 中无源码 | 只有外部 Gateway 的清理/健康检查脚本 | 企业微信 WebSocket/API、bot id/secret、QwenPaw | 运维壳存在，Channel/Gateway 实现缺失 |
| 微信/微信客服 | 有 `wechat` 配置，已禁用；另有历史微信客服文档 | `channels/` 中无源码；Gateway 实现未导出 | 无可启动脚本 | 微信回调/API、公共 HTTPS/Tailscale Funnel、QwenPaw HTTP/CLI | 配置与历史方案并存，实际适配器边界需要恢复确认 |

## Console

- `configs/agent.json` 中只有 Console 为启用状态。
- 没有独立 Console 服务入口；根据现有 README，它应随 `qwenpaw start` 启动。
- 仓库没有 QwenPaw CLI、Channel Loader 或 AgentScope 运行时源码，因此“配置启用”不等于“当前本地可运行”。

## Telegram

- 配置项包含启用开关、bot token、base URL、HTTP 代理、流式开关等；当前为禁用，敏感字段没有作为启动参数输出。
- `channels/` 只有占位文件，没有 Telegram adapter 源码或启动脚本。
- 被忽略的历史运行记录中出现 `/run/.../hermes`、`/app/user-packages/...` 等外部组件路径，说明原运行时可能由 Hermes/云端插件提供；这些组件不在本仓库。
- 生产依赖包括 Telegram Bot API、可达网络或代理、凭据安全注入，以及已验证版本的外部 Channel 运行时。

## 企业微信

- `configs/agent.json` 中有 `wecom` 配置，当前禁用，流式输出也禁用。
- `scripts/cleanup_old_gateways.sh` 与 `scripts/healthcheck_v345_final.sh` 只操作 `/run/.../wecom-kf` 下的外部文件和进程，不能启动一个新 Gateway。
- `digest/` 的历史 runbook 记录过 WebSocket/API、回调、轮询兜底、SQLite 状态机、Tailscale Funnel 和图片消息链路，但对应 Gateway Python 源码、数据库 schema 初始化器及部署单元没有导出。
- 外部依赖包括企业微信 API/WebSocket、bot id/secret、模型/Agent 服务，以及部分历史方案中的公网回调和 Tailscale。

## 微信与微信客服

- QwenPaw 配置中存在通用 `wechat` Channel，当前禁用；仓库没有对应 adapter。
- 历史文档还描述了微信公众号被动回复 Gateway，以及企业微信“微信客服” Gateway。两者协议、凭据和生命周期不同，不能把通用 `wechat` 配置直接等同于现有微信客服实现。
- 历史微信公众号方案依赖回调验签、同步 XML 回复、QwenPaw CLI/HTTP API 与 Tailscale Funnel；相关 Gateway 源码未随导出包提供。
- 历史企业微信客服方案依赖 `kf/sync_msg`、`kf/send_msg`、媒体上传、SQLite 去重状态和公网回调；实际实现同样缺失。

## 恢复优先级

1. 先恢复 QwenPaw/AgentScope 精确版本及 Channel Loader，验证 Console。
2. 从原部署制品恢复 Telegram/Hermes、企业微信 Gateway、微信公众号 Gateway 的源码和启动单元，并核对许可证与版本。
3. 为每个 Channel 建立独立配置 schema、脱敏示例和离线契约测试。
4. 在沙箱或测试租户中验证回调、轮询、断线重连与幂等，再考虑启用生产配置。
5. 最后统一消息模型和 Streaming；当前不修改任何 Channel 或流式逻辑。

---
description: WeCom 微信客服 Gateway 蓝绿部署与 Funnel 切流 runbook：多版本并行、禁止 kill、验收清单通过才切流、callback
  缺失时 polling 兜底、V1→V3.4.3 七次以上验证
name: WeCom Gateway 蓝绿部署与 Funnel 切换流程
---

# WeCom Gateway 蓝绿部署与 Funnel 切换流程

## 触发条件

部署新版本 WeCom 微信客服 Gateway 时，采用蓝绿并行模式，零停机接管生产流量。

## 前置条件

- Tailscale Funnel 已启用，SBS 节点 HTTPS 443 根路径可用
- 旧版本 Gateway 已运行在已知端口上（8787→8796 递增）
- 数据库沿用 `gateway-v32.db`（禁止新建空库或DROP TABLE）
- 企微后台配置（回调地址、认证）无需修改

## 步骤

1. **创建新版本文件**：基于最新稳定版复制，修改监听端口（端口池 8787→8796，禁止复用已用端口）。
2. **静态验收（全部通过才可继续）**：
   - `python3 -m py_compile` 通过
   - 本地 `http://127.0.0.1:<port>/healthz` 返回 `OK`
   - 数据库迁移：`PRAGMA table_info` 检查 + `ALTER TABLE` 增量添加缺失列，保留全部历史 `completed` 记录
   - 图片压缩函数 `prepare_wecom_image` 真实调用，输出 `<= 1.9MB`
   - `media/upload` 真实测试返回 `errcode=0` 且 `media_id` 非空
3. **启动新进程**：`nohup python3 <new_version>.py &`，写入独立 PID 文件，确认进程运行。
4. **Funnel 切流**：
   ```
   funnel --https=443 --set-path=/ --yes off
   funnel --https=443 --set-path=/ --bg --yes http://127.0.0.1:<new_port>
   ```
   公网域名 `qwenpaw-sbs-prod-dj2gm.tail7c303e.ts.net` 不变；旧版本进程继续运行。
5. **公网 healthz 验证**：`curl https://<domain>/healthz` 返回 HTTP/2 200 OK。
6. **Callback 缺失兜底**（如 V3.4.1 实测 callback 穿透失败时）：基于新版本创建 +30s 轮询版本，独立端口，daemon thread 调用 `kf/sync_msg`，cursor 持久化到 JSON 文件，复用同一 `processed_messages` 去重；**同一时间只允许一个轮询实例运行**。
7. **停止旧实例**（可选，非强制）：在确认新版本生产稳定后，仅停止最旧的实例；禁止 `kill/pkill`，使用正常进程终止。

## 关键约束

- **禁止 kill/pkill**：任何版本都不强制终止进程，靠 Funnel 路由自然切流。
- **禁止修改企微后台**：回调地址、Agent 配置等在 Funnel 层透明切换。
- **禁止提前切 Funnel**：验收清单任一项未通过不得切流；若公网 DNS 解析失败，以本地 healthz + 静态检查为准，DNS 恢复后补公网验证。
- **数据库零丢失**：所有 V3.x 版本共享 `gateway-v32.db`，迁移仅增量 `ALTER TABLE`，禁止 `DELETE` / `DROP` / `CREATE OR REPLACE`。
- **轮询竞争防护**：`sync_cursor_<version>.json` 原子写入，确保同一 `msgid` 不会被双实例重复处理。
- **U1 图片生成**：直接调用 `sn_agent_runner.py`（非 QwenPaw agent），`sys.executable` + `cwd=BASE`，最多 2 次重试（首次失败 sleep 5s），日志脱敏。

## 失败模式

- **Callback 未穿透 Funnel**：企业微信回调 POST 未到达新实例，但 `sync_msg` 能拉取到消息 → 必须部署 polling 兜底版本，禁止手动 `sync_msg` probe 代替。
- **公网 DNS 解析失败**：`qwenpaw-sbs-prod-dj2gm.tail7c303e.ts.net` 外部无法解析 → 以本地 Funnel 配置 + 本地 healthz 为准，DNS 恢复后补验证，不阻断切流。
- **service_state API 404**：`/cgi-bin/kf/get_service_state` 返回 404，正确 URL 为 `/cgi-bin/kf/service_state/get`（POST）。
- **U1 生成超时或失败**：仅返回固定文本"抱歉，图片生成暂时失败了，请稍后再试。"，不暴露 JSON / prompt / stderr / traceback；`generated_images` / `processed_messages` 标记 `failed`。
- **图片压缩超限**：质量逐级递减（92→88→82→76→70）+ 分辨率逐级缩小（2048→1800→1600→1400→1200），每次保存后校验 `<= 1.9MB`；始终失败则记录 `image prepare failed`，不调用 `media/upload`。

## 端口版本映射（V1→V3.4.3 已验证）

| 版本 | 端口 | 关键特征 |
|------|------|----------|
| V1   | 8787 | 基础回调解密 + AI 收发 |
| V2   | 8788 | 仅回调解密壳子，无 AI |
| V3   | 8789 | AES 导入缺失（V3.1 修复） |
| V3.1 | 8790 | 增加 processing/completed/failed 状态机 + ACK |
| V3.2 | 8791 | 修复 external_userid 判断顺序 + sync_msg 过滤 |
| V3.3 | 8792 | 修复 service_state URL + 历史消息保护 |
| V3.4 | 8793 | 图片路由 + U1 Fast + 图片压缩 + media/upload |
| V3.4.1 | 8794 | 蓝绿切流测试，callback 穿透失败 |
| V3.4.2 | 8795 | 新增 30s polling 兜底 + cursor 持久化 |
| V3.4.3 | 8796 | U1 重试 2 次 + 日志脱敏 + 失败安全回退 |

## Sources

- 这一流程的首个完整实例见于 [[memory/2026-08-21/tailscale-funnel-and-qwenpaw-setup.md|该会话记录]]，其中记录了 V1→V3.3 的逐步部署、Funnel 根路径切流操作命令序列，以及禁止 kill/pkill、禁止修改企微后台、禁止提前切 Funnel 这三条核心约束。
- V3.4 版本的具体验收清单、图片压缩参数（quality 92→70 + 分辨率 2048→1200 逐级递减）、media/upload MIME 类型规范和数据库兼容迁移逻辑，见于 [[memory/2026-08-21/wecom-kf-gateway-v34-deployment.md|该部署记录]]。
- V3.4.2 的 30 秒轮询兜底方案、cursor 持久化设计、双实例竞争防护，以及 V3.4.3 的 U1 重试与日志脱敏强化，见于 [[memory/2026-08-21/wecom-kf-v343-deployment.md|该版本部署记录]]。

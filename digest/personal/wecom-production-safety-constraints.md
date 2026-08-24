---
description: 本项目 WeCom 生产环境操作铁律：禁止 kill/pkill、日志脱敏、不修改企微后台、安全注入 U1 环境变量、验收通过才切 Funnel。
name: WeCom 生产环境安全约束集
---

# WeCom 生产环境安全约束集

## 1. 禁止 kill/pkill，多版本并行靠蓝绿切换
**Rule**: 任何 Gateway 版本（8787→8796）均不允许执行 `kill`/`pkill` 终止进程；新版本部署采用蓝绿并行，通过 Funnel 根路径切流接管流量，旧版本进程自然保留。
**Why**: 强制终止会导致 SQLite 数据库损坏、消息状态丢失、用户会话中断；蓝绿切换保证零停机且可回滚。
**How to apply**: 部署新版本时仅启动新进程并切换 Funnel 路由；确认新版本稳定后，如需回收资源仅停止最旧实例且使用正常进程终止。同一时间只允许一个轮询（polling）实例运行，通过独立 `sync_cursor_<version>.json` 原子写入防止竞争。

## 2. 日志与输出必须脱敏，禁止泄露敏感凭证
**Rule**: 所有日志（stdout/stderr/文件日志）禁止输出 `TOKEN`/`AESKEY`/`APP_SECRET`/`access_token`/`SN_API_KEY`；stdout/stderr 需经 `sanitize_log_text()` 脱敏（屏蔽 `api_key`/`apikey`/`token`/`secret`/`Authorization`/`Bearer`）。
**Why**: 生产环境日志可能被多人或下游系统查看，凭证泄露会导致企业微信账号或 SenseNova 服务被滥用。
**How to apply**: Gateway 代码中所有 `print`/`logging` 调用必须经过脱敏函数；U1 生图子进程的 stderr 捕获后必须经 `sanitize_log_text()` 再写入日志；失败回退时仅发送固定文本，禁止将 agent_reply/JSON/prompt/stderr/traceback 暴露给用户。

## 3. 不修改企业微信后台配置
**Rule**: 不得修改企业微信后台的回调地址、客服账号配置、Agent 绑定或权限设置。
**Why**: 企微后台变更具有全局影响且难以回滚；Gateway 侧通过 Funnel 层透明切换即可实现流量接管，无需触碰后台。
**How to apply**: 所有生产变更限制在 Gateway 代码、Funnel 路由和本地 `.env` 文件范围内；如需更新回调地址，仅在 Tailscale Funnel 层修改路径映射。

## 4. U1 生图环境变量必须通过 load_sensenova_env() 安全注入
**Rule**: subprocess 调用 U1（`sn_agent_runner.py`）时，不得将 SenseNova 凭证硬编码在命令行或代码中；必须通过 `load_sensenova_env()` 从独立 `.env` 文件加载环境变量，且禁止打印 Key。
**Why**: 命令行参数会被 `ps`/`/proc` 泄露；硬编码凭证会进入代码仓库历史。
**How to apply**: U1 调用统一使用 `sys.executable` + `cwd=BASE` + 经过 `load_sensenova_env()` 清洗后的 `env` 参数；`.env` 文件不得进入版本控制。

## 5. 未经完整验收禁止切 Funnel
**Rule**: 新版本 Gateway 在以下验收清单全部通过前，禁止将 Funnel 根路径切到新端口：`py_compile` 通过、本地 healthz 返回 `OK`、数据库增量迁移完成且旧 `completed` 记录保留、`prepare_wecom_image` 真实压缩 `<= 1.9MB`、`media/upload` 真实测试 `errcode=0` 且 `media_id` 非空。
**Why**: 提前切流会导致生产消息进入未验证代码路径，引发消息丢失、格式错误或数据库损坏。
**How to apply**: 每次版本发布严格按验收清单逐项核对；若公网 DNS 解析失败，以本地 healthz 与 Funnel 配置状态为准，DNS 恢复后补公网验证，不阻断切流。同一时间只允许一个轮询实例运行，避免双实例竞争处理同一 `msgid`。

## 相关约定

- 蓝绿部署与 Funnel 切流的具体 runbook 见 [[digest/procedure/wecom-gateway-bluegreen-funnel.md]]。
- 图片消息端到端处理（含 U1 调用、压缩、upload、send）的详细流程见 [[digest/procedure/wecom-image-message-pipeline.md]]。
- SQLite 增量迁移与 `processing`/`completed`/`failed` 状态机约定见 [[digest/procedure/wecom-gateway-sqlite-migration-and-state-machine.md]]。
- 企微 API 已知陷阱（如 `service_state` 正确 URL、callback 穿透失败兜底）见 [[digest/wiki/wecom-kf-api-traps-and-workarounds.md]]。

## Sources

- 这五条安全约束的首个完整实例与全程执行记录见于 [[memory/2026-08-21/tailscale-funnel-and-qwenpaw-setup.md|该会话记录]]，其中 V1→V3.3 的逐步部署、Funnel 根路径切流操作命令序列，以及禁止 kill/pkill、禁止修改企微后台、禁止提前切 Funnel 三条核心约束均被实际执行且无违背。
- V3.4 版本的图片压缩参数（quality 92→70 + 分辨率 2048→1200 逐级递减）、`media/upload` MIME 类型规范、`load_sensenova_env()` 安全注入方式及数据库兼容迁移逻辑，见于 [[memory/2026-08-21/wecom-kf-gateway-v34-deployment.md|该 V3.4 部署记录]]。
- V3.4.3 对 U1 重试机制（最多 2 次、首次失败 sleep 5s）、`sanitize_log_text()` 日志脱敏函数及失败安全回退文本的最终实现，见于 [[memory/2026-08-21/wecom-kf-v343-deployment.md|该 V3.4.3 部署记录]]。

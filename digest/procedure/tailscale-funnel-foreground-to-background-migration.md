---
description: 将 Tailscale Funnel 从 Foreground session 迁移到 Background session 的原子化 runbook：通过
  LocalAPI serve-config POST（ETag 校验）删除 Foreground 并原子确认 count=0，随后建立 --bg funnel
  并验证 healthz 连通性。
name: Tailscale Funnel Foreground→Background 原子迁移
---

# Tailscale Funnel Foreground→Background 原子迁移

## 触发条件

需要将当前通过 `tailscale funnel --https=443 ...`（前台 CLI 进程）承载的 Funnel 切换为由 tailscaled 内建管理的 Background session，以消除前台 CLI 进程依赖并实现零公网中断。

## 前置条件

- tailscaled 运行且 LocalAPI socket 可访问（默认 `/tmp/tailscaled_final.sock`）
- 已知 Foreground session ID（通过 LocalAPI GET 获取）
- 当前 Foreground session 的 target（例如 `http://127.0.0.1:<port>`）
- ETag 值（GET 响应头 `ETag` 字段）
- 目标 Background 端口对应的服务已通过本地 `/healthz` 验证

## 步骤

1. **只读确认当前状态**：连续多次 GET `http://localhost:<localapi_port>/localapi/v0/serve-config`，确认 FOREGROUND_COUNT、SESSION_PRESENT、TARGET 字段符合预期。
2. **生成 after-config JSON**：以当前配置为基准，移除 Foreground session 字段，保留 Web/Handlers 和 AllowFunnel 顶层结构；计算期望的新 FOREGROUND_COUNT=0。
3. **POST serve-config（首次）**：以 `If-Match: <ETag>` 头将 after-config 写入 LocalAPI；若因 socket 临时不可达失败（curl exit code 7 / HTTP 000），记录错误但不执行任何 kill/reset。
4. **安全续跑**：重新 GET 验证配置未变，重新读取最新 ETag，重新生成 after-config，再次 POST。
5. **原子确认删除**：GET 验证 FOREGROUND_COUNT=0，OLD_SESSION_REMOVED=True；若存在前台 CLI 进程，确认其已自行退出（PPID=1 收养或自然终止）。
6. **建立 Background Funnel**：执行 `tailscale funnel --bg --yes --https=443 --set-path=/ http://127.0.0.1:<bg_port>`；确认 BACKGROUND_TARGET 写入、FOREGROUND_FINAL_COUNT=0、ALLOW_FUNNEL=True。
7. **公网健康验证**：`curl https://<domain>/healthz`；若首次返回 SSL error 000，sleep 5s 后重试，直至 HTTP 200。
8. **下游服务验证**：确认 V345 等下游进程健康、polling 循环正常，无 traceback。
9. **配置归档**：将最终 Funnel JSON 写入 `/tmp/<name>-final-funnel.json`，含 Web/Handlers 与 AllowFunnel 快照。

## 失败模式

- **POST 连接失败（curl 7）**：LocalAPI socket 暂时不可达；禁止 kill/reset，等待后重试。
- **ETag 不匹配**：配置已被其他写入变更；重新 GET 获取新 ETag 再提交。
- **公网瞬时 404**：Funnel handler 在重配瞬间短暂失效，属正常现象；sleep 5s 重试即可。
- **/health → 404，/healthz → 200**：应用可能仅暴露 `/healthz`；以 `/healthz` 为准。

## 关键约束

- 禁止 `kill`/`pkill`/`reset` 操作 tailscaled 或前台 Funnel CLI 进程；删除 Foreground 后旧进程应自行退出。
- 分步验证：每一步检查返回码和状态字段，异常立即停止。
- 不复用过期 ETag：每次重试必须重新 GET 最新 ETag。

## Sources

- 这一流程的首次完整执行记录见于 [[memory/2026-08-22/tailscale-funnel-migration-sbs.md|该会话记录]]，其中详细记录了 SBS 场景下从 Foreground session `e93f5e6aba8c613e`（target 8797）到 Background Funnel（target 8798）的全过程，包括 LocalAPI serve-config POST 的 ETag 机制、原子删除验证、前台 CLI 进程自行退出确认，以及公网健康检查重试流程。
- 该迁移涉及 WeCom 生产环境操作，需遵守 [[digest/personal/wecom-production-safety-constraints.md|WeCom 生产环境安全约束集]] 中"禁止 kill/pkill"及"未经完整验收禁止切 Funnel"两条铁律；V345 等服务在迁移后的存活验证可参照 [[digest/procedure/wecom-gateway-bluegreen-funnel.md|WeCom Gateway 蓝绿部署与 Funnel 切换流程]] 中的健康验收清单执行。
- 公网瞬时 404 现象已在迁移记录中确认为 Funnel 重配过程中的正常 handler 切换行为，无需干预。

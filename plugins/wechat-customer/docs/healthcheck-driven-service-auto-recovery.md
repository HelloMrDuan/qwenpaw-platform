---
description: 无 systemd/supervisord 托管的长期运行服务的自动恢复 runbook：独立 healthcheck 脚本轮询 /healthz，进程不存在时后台启动并最多等待
  15 秒，healthz 仍失败时仅报错不强行 kill；heartbeat/AsyncIOScheduler 不可靠不应作为唯一手段；每次版本升级后需显式清理旧版本僵尸进程。
kind: procedure
name: Healthcheck-Driven Service Auto-Recovery
---

# Healthcheck-Driven Service Auto-Recovery

## Trigger / when to use

长期运行服务由 nohup 手动启动、无 systemd / supervisord 托管（如 V345 微信客服网关），需独立自动恢复机制，且不依赖 heartbeat 或 AsyncIOScheduler 调度。

## Pre-conditions

- 服务暴露 `http://127.0.0.1:<port>/healthz`，健康时返回 HTTP 200。
- 已知正确的启动命令与工作目录。
- 目标端口未被占用。

## Steps

1. **部署独立 healthcheck 脚本**（如 `healthcheck_<service>.sh`），以 cron 或外部调度器按固定间隔调用；脚本本身不依赖 heartbeat 或 AsyncIOScheduler 触发。
2. **脚本轮询 healthz**：`curl http://127.0.0.1:<port>/healthz` 返回 200 → `exit 0`。
3. **进程不存在时拉起服务**：healthz 失败且对应进程不存在 → 后台启动服务（`nohup ... &`），最多轮询 15 秒等待 healthz 恢复。
4. **15 秒后仍不健康** → 报错至 stderr，`exit 1`；不强行 kill，不重启进程。
5. **进程存在但 healthz 失败** → 报错至 stderr，`exit 1`；不 kill、不重启（避免干扰正在工作的实例）。
6. **每次版本升级后显式清理旧版本僵尸进程**：向旧版本 PID 发送 `SIGTERM`，等待后验证旧进程已终止、旧游标文件时间戳未变化；旧代码无暂停/禁用机制，会持续空转轮询。

## Failure modes / caveats

- **heartbeat / AsyncIOScheduler 不可靠**：internal job 在当前环境下事件循环未触发，heartbeat 任务不执行；不应作为唯一恢复手段。
- **不强行 kill 健康进程**：即使 healthz 失败，若进程仍存活，仅报错不终止——这与生产环境禁止 kill/pkill 的约束一致；详见 [[digest/personal/wecom-production-safety-constraints.md]] 中"禁止 kill/pkill，多版本并行靠蓝绿切换"规则。
- **15 秒超时为经验值**：若服务冷启动超过 15 秒，脚本会误判失败，需人工介入。
- **版本升级必做清理**：旧版本进程无暂停/禁用机制，每次升级后必须显式 SIGTERM 清理，否则旧实例持续空转轮询并竞争消息。

## Sources

- 这一流程的直接实践记录见于 [[memory/2026-08-22/v345-healthcheck-upgrade.md|V345 healthcheck 脚本升级与验证会话]]，其中完整记录了脚本重写逻辑（healthz 通过→exit 0、进程不存在→后台启动并最多等待 15 秒、healthz 仍失败→仅报错不 kill）、升级后清理 V341–V344 僵尸进程的操作及验证结果，以及旧版本无暂停/禁用机制导致空转轮询的根本原因分析。
- 生产环境中禁止 kill/pkill 的核心约束及蓝绿切换上下文，见于 [[digest/personal/wecom-production-safety-constraints.md|WeCom 生产环境安全约束集]]，该文件明确禁止强制终止 Gateway 进程，与 healthcheck 脚本"healthz 失败时不强行 kill"的设计原则相互印证。
- 微信客服 Gateway 蓝绿部署与多版本并行的整体流程，见于 [[digest/procedure/wecom-gateway-bluegreen-funnel.md|WeCom Gateway 蓝绿部署与 Funnel 切换流程]]，为 healthcheck 脚本提供了端口分配和版本治理的背景上下文。
- 2026-08-23 的运维记录验证了该流程的实际效果：`wecom_kf_gateway_v345.py` 进程缺失后，`healthcheck_v345.sh` 成功将其重新拉起并恢复 HTTP 200，见于 [[memory/2026-08-23/ops-update-20260823.md|当日运维事件汇总]]。

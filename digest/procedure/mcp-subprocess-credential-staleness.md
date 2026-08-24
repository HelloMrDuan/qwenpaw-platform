---
description: MCP 子进程继承父进程环境变量后不再自动刷新；若 credentials.yaml 在子进程启动后才写入新 API Key，运行中子进程将持续表现为
  keyless，reload 配置也不会自动重启子进程。
kind: procedure
name: MCP Subprocess Credential Staleness Pattern
---

## Trigger / when to use

需要为第三方搜索 provider（如 Tavily）或其他 MCP 服务配置 API Key / Secret，或 credentials.yaml 已更新但服务仍表现为 keyless / 认证失败。

## Steps

1. **确认安全约束**：Agent 因安全规则无法代存或读取 API Key / Secret 等私密凭证，也无法通过交互式提示符输入（当前环境无真实 TTY）。
2. **用户提供密钥**：由用户将密钥直接粘贴到下一条消息中，避免任何持久化中间存储。
3. **写入 credentials.yaml**：系统将密钥写入 `credentials.yaml`，对应服务的 `endpoint.env` 以 `source: credential` 方式引用。
4. **Reload MCP 配置**：执行 reload 使 MCP 配置层读取新 credentials。
5. **重启相关 MCP 子进程**：Reload 不会自动重启已运行的子进程；子进程在启动时继承父进程环境变量后不再自动刷新，需显式重启相关 MCP 子进程以使其继承新环境变量。
6. **验证子进程已拿到新变量**：通过 `/proc/$PID/environ` 只读确认目标环境变量（如 `TAVILY_API_KEY`）存在于子进程环境中，**严禁打印真实值或长度**。
7. **功能性验证**：通过实际请求确认服务已从 keyless 恢复为正常认证状态。

## Pre-conditions / inputs

- 用户已将 API Key 粘贴到消息中（Agent 不得代存）。
- 已知目标环境变量名（如 `TAVILY_API_KEY`）。
- 有权限写入 `credentials.yaml` 并执行 MCP reload。
- 有权限读取 `/proc/$PID/environ` 验证子进程环境变量。
- 确认 `credentials.yaml` 写入时间晚于子进程启动时间（用于 staleness 诊断）。

## Failure modes / caveats

- **reload 不会自动重启子进程**：即使 MCP 配置重新加载，运行中的子进程不会重新读取环境变量，这一点与 [[digest/procedure/healthcheck-driven-service-auto-recovery.md|Healthcheck-Driven Service Auto-Recovery]] 中"无托管进程需显式拉起"的逻辑一致。
- **父进程时间差**：子进程启动时刻早于 credentials 写入时刻是 staleness 的典型特征；此类问题不会自愈。
- **禁止直接读取真实 Key**：检查 `/proc/$PID/environ` 时仅确认变量是否存在，严禁打印完整值或长度——这与 [[digest/personal/wecom-production-safety-constraints.md|WeCom 生产环境安全约束集]] 中凭证脱敏要求一致。
- **安全约束不可绕过**：Agent 不得代存、读取或回显 API Key；交互式提示符在当前环境无真实 TTY，无法作为输入通道。

## Sources

- 2026-08-22 V345 健康检查升级会话中，尝试通过交互式提示符配置 Tavily API Key 被安全规则阻止，最终确立"用户将 key 粘贴到下一条消息 → 系统写入 credentials.yaml → reload MCP 配置"的可行流程，并明确配置完成后需重启 MCP 子进程以继承新环境变量，支持本流程的初始配置步骤，见于 [[memory/2026-08-22/v345-healthcheck-upgrade.md|V345 healthcheck 脚本升级与验证会话]]。
- 同一会话记录了为何交互式输入不可用：当前环境无真实 TTY，`read -rsp` 提示符无法正常工作，这进一步确认了"用户粘贴到消息"是唯一可行的输入通道，同样见于 [[memory/2026-08-22/v345-healthcheck-upgrade.md|V345 healthcheck 脚本升级与验证会话]]。
- 2026-08-23 的 Tavily MCP Keyless 调试记录从反面验证了本流程的关键步骤：`tavily_mcp__tavily_search` 子进程启动时间（Sat Aug 22 23:49:36）早于 `credentials.yaml` 写入新 Key 的时间（2026-08-23 00:06:01），导致继承空 `TAVILY_API_KEY` 并持续表现为 keyless；reload 后无新进程出现，证实必须显式重启子进程，见于 [[memory/2026-08-23/tavily-mcp-keyless-debug.md|Tavily MCP Keyless 调试记录]]。
- 同一调试记录还确认了 `tavily-mcp` npm 包实际读取的环境变量名为 `TAVILY_API_KEY`，与 `tavily_search.yaml` 中 `endpoint.env` 的 credential 引用路径一致，支持本流程中"写入 credentials.yaml → reload → 重启子进程"的端到端验证逻辑，同样见于 [[memory/2026-08-23/tavily-mcp-keyless-debug.md|Tavily MCP Keyless 调试记录]]。

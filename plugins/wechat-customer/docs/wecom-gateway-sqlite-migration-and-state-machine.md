---
description: WeCom 微信客服 Gateway 的 SQLite 增量 schema 迁移 runbook 与消息状态机三态约定：启动时 PRAGMA
  table_info 检查、仅 ADD COLUMN、禁止覆盖旧表、WAL/busy_timeout、processing→completed→failed 严格流转、generated_images
  独立生命周期、processed_messages 按 msgid 去重、首次启动历史检查防切流重处理。
name: SQLite 增量 Schema 迁移与状态机约定
---

# SQLite 增量 Schema 迁移与状态机约定

## 触发条件

Gateway 服务启动或版本升级时，对现有 SQLite 数据库执行安全迁移并初始化消息处理状态机。

## 前置条件

- 数据库文件（如 `gateway-v32.db`）已存在且可读写。
- 代码中已定义目标表结构（`processed_messages`、`generated_images` 等）。
- 首次启动或版本切换场景下需执行历史消息状态检查。

## 步骤

1. **启动迁移检查**：对每个目标表执行 `PRAGMA table_info(<table>)`，枚举当前已存在列。
2. **增量添加列**：对缺失列执行 `ALTER TABLE ADD COLUMN <col> <type>`；**禁止** `DROP TABLE`、`DELETE`、`CREATE OR REPLACE` 覆盖旧表，防止历史数据丢失。
3. **启用 WAL 与 busy_timeout**：执行 `PRAGMA journal_mode=WAL` 和 `PRAGMA busy_timeout=5000`，提升并发读写容错。
4. **创建 generated_images 表**：独立记录图片生命周期字段（`upload_status`、`send_status`），与消息状态机解耦。
5. **配置去重**：`processed_messages` 按 `msgid` 去重；无论状态为 `completed`、`processing` 或 `failed`，均 skip 重复消息。
6. **执行状态机流转**：
   - Agent 调用前写入 `processing`。
   - 仅当最终微信消息 `errcode == 0` 时写入 `completed`。
   - 任何关键失败分支统一写入 `failed`。
7. **首次启动历史检查**：启动时检查最近 6 条消息状态；若切流后消息已存在于 `processed_messages` 中，跳过重新处理。

## 失败模式与 caveats

- **数据丢失风险**：`DROP TABLE` / `DELETE` / `CREATE OR REPLACE` 会破坏历史对话与去重记录，绝对禁止。
- **状态提前标记**：`completed` 必须等待最终 `errcode==0`，提前写入会导致用户收到虚假成功反馈且无法回退到 `failed`。
- **切流重处理**：蓝绿切流后旧实例已处理的消息可能再次进入新实例，首次启动历史检查是唯一防护。
- **双实例轮询竞争**：若存在多个 polling 实例，需通过独立 `sync_cursor_<version>.json` 原子写入 + `processed_messages` 去重防止重复处理。

## Sources

- 这一迁移模式与状态机约定的首个完整实现见于 [[memory/2026-08-21/wecom-kf-gateway-v34-deployment.md|该 V3.4 部署记录]]，其中记录了 `PRAGMA table_info` + `ALTER TABLE` 增量迁移 `processed_messages` 四列（`open_kfid`、`msgtype`、`content_hash`、`updated_at`）、`generated_images` 表独立生命周期字段、`journal_mode=WAL` / `busy_timeout=5000`、`completed` 状态时机修正（仅 `errcode==0` 时写入）以及首次启动历史检查逻辑。
- V3.4.3 对 U1 失败回退时 `generated_images upload_status='failed' send_status='failed'` 与 `processed_messages='failed'` 的最终落库实现，见于 [[memory/2026-08-21/wecom-kf-v343-deployment.md|该 V3.4.3 部署记录]]，验证了状态机在关键失败分支的一致性。
- 与此迁移约定共享同一 Gateway 的蓝绿部署流程（含 `gateway-v32.db` 零丢失约束、禁止 kill/pkill、Funnel 切流后防重复处理），见 [[digest/procedure/wecom-gateway-bluegreen-funnel.md|WeCom Gateway 蓝绿部署与 Funnel 切换流程]]。
- 与此状态机共享 `completed`/`failed` 标记逻辑的图片消息端到端流水线，见 [[digest/procedure/wecom-image-message-pipeline.md|微信图片消息端到端处理流水线]]。
- callback 投递不可靠需 polling 兜底、cursor 持久化防竞争的历史背景，见 [[digest/wiki/wecom-kf-api-traps-and-workarounds.md|WeCom kf API 已知陷阱与绕过方案]]。

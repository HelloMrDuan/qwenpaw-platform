# Historical Channel Migration

## 1. 目标

Phase 5.1 将已找到的历史 Channel/Gateway 源码整理到 Extension Architecture，建立可审计的来源基线。

本阶段只完成：

- 文件整理；
- Extension 目录规范化；
- README 与依赖说明；
- 原始路径、新路径和缺口记录。

本阶段没有修改恢复源码、接入 Runtime、修改 Gateway、Message Contract 或 Streaming。

## 2. 来源基线

| 项目 | 值 |
| --- | --- |
| 恢复包 | `channel-runtime-recovery-export.zip` |
| SHA-256 | `35fd917257b4bcb0862d7a76ef296985d265bc7a70f359601f2748e603aa8300` |
| 恢复包根 | `channel-runtime-recovery-export/` |
| 导入策略 | 选择性复制，`recovered/` 文件保持字节不变 |

## 3. 路径映射

用户给出的来源名称是能力逻辑名称；ZIP 实际目录沿用了历史运行目录。迁移采用实际 ZIP 路径：

| 能力 | 逻辑来源 | 实际 ZIP 来源 | 新目录 |
| --- | --- | --- | --- |
| Hermes | `channel-runtime-recovery-export/hermes/` | `hermes/hermes-agent-main/`、`hermes/fast_route.py`、`hermes/run_image_and_reply.sh` | `plugins/hermes/` |
| 企业微信 | `channel-runtime-recovery-export/wecom-node/` | `hermes/wecom-node/`、`telegram/start_wecom_bridge.sh` | `plugins/wecom/` |
| 微信客服 | `channel-runtime-recovery-export/wecom-kf/` | `wecom/`、相关 `docs/` | `plugins/wechat-customer/` |
| WeChat MP | `channel-runtime-recovery-export/wechat-mp/` | `wechat/` | `plugins/wechat-mp/` |
| Telegram | `hermes/telegram_bridge*` | `telegram/telegram_bridge*.py`、`telegram/start_bridge.sh` | `adapters/telegram/` |

## 4. 迁移结果

| 组件 | 当前状态 | 原运行入口 | 主要依赖 | 缺失项 |
| --- | --- | --- | --- | --- |
| Hermes | `RECOVERED_SOURCE_ONLY` | `hermes`、`python -m gateway.run`、Docker | Python 3.11、Node 26、uv、系统工具 | runner、wrapper、pyproject、uv.lock |
| 企业微信 | `RECOVERED_SOURCE_ONLY` | `node wecom_bridge.mjs` | Node、`@wecom/aibot-node-sdk`、Hermes | lock、SDK 版本、runner、配置模板 |
| 微信客服 | `RECOVERED_SOURCE_ONLY` | `healthcheck_v345.sh` / Python Gateway | Python、Crypto、Pillow、SQLite、QwenPaw | runner、数据库、cursor、配置模板 |
| WeChat MP | `RECOVERED_SOURCE_ONLY` | `python3 wechat_mp_gateway.py` | Python 标准库、QwenPaw CLI/API | 配置模板、服务脚本、生产版本确认 |
| Telegram | `RECOVERED_SOURCE_ONLY` | `start_bridge.sh` | Python 标准库、Hermes、Telegram API | runner、wrapper、配置模板、环境锁 |

`RECOVERED_SOURCE_ONLY` 只表示源码基线已经整理，不等于 `READY_FOR_MIGRATION` 或可部署。完整性状态仍以 `CHANNEL_RECOVERY_COMPLETENESS_REPORT.md` 为准。

## 5. 导入与排除规则

已导入：

- 历史 Python、MJS、Shell 源码；
- Hermes 工程源码、测试、许可、静态资源和已有配置示例；
- 微信客服相关历史运行文档；
- 每个 Extension 的 README。

已排除：

- `telegram_bridge.pid`；
- Hermes 历史 `log.txt`；
- `wecom/generated/` 探测图片；
- `.env`、token、secret；
- DB、WAL/SHM、cursor、session、日志；
- 原 Workspace Agent 配置。

企业微信源码从 Hermes 历史运行目录拆分为独立 Plugin，不在 `plugins/hermes/` 重复保存。

## 6. 目录规范

```text
plugins/<name>/
├── recovered/     # 未修改的历史来源基线
├── docs/          # 可选的历史运行文档
└── README.md       # 来源、依赖、缺口和边界

adapters/telegram/
├── recovered/
└── README.md
```

未来新增的 Extension Contract、测试、配置 schema 和 packaging 文件必须位于 `recovered/` 外部。不得直接修改来源基线来适配 Runtime。

## 7. 导入校验

| 校验项 | 结果 |
| --- | --- |
| ZIP 来源文件 | 3516 |
| 来源文件总字节 | 59,442,880 |
| 工作区文件与 ZIP SHA-256 对比 | 3516/3516 一致，0 mismatch |
| Git index blob 与工作区原始字节 | 3516/3516 一致，0 mismatch |
| ZIP 可执行位映射到 Git | 39 个已导入可执行文件全部保留 |
| 高置信 token/private key 扫描 | 未发现真实 token 或私钥；命中的 private-key 文本均为检测/脱敏代码字符串 |
| 平台离线回归 | `unittest discover -s tests`：36 项通过 |
| `git diff --check` | 恢复的 Hermes 上游源码含原始尾随空格；为保持字节基线不作清理，本次新写文档单独通过检查 |

恢复 ZIP 已加入 `.gitignore`，不进入 Git。

## 8. 后续接入计划

1. 从 NAS/旧容器补齐 P0 缺失文件；
2. 重跑 Recovery Completeness Audit；
3. 为每个 Extension 建立独立版本、CHANGELOG 和 dependency lock；
4. 在 `recovered/` 外建立包装层和离线测试；
5. 定义 config template，secret 只从部署环境注入；
6. 构建不可变 Release Package；
7. Cloud staging 验证；
8. 经单独评审后才接入 Runtime。

## 9. 回滚

本阶段没有 Runtime 连接。回滚只需回退 Historical Channel Migration 提交，不影响现有 Agent、Channel 或 PDF Editor。

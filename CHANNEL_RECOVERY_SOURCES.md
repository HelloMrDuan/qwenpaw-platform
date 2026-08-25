# Channel Recovery Sources

> 状态更新（2026-08-25）：本报告完成后，项目根目录新增并验证了
> `channel-runtime-recovery-export.zip`（SHA-256：
> `35fd917257b4bcb0862d7a76ef296985d265bc7a70f359601f2748e603aa8300`）。
> 该恢复包包含此前未找到的 Channel 源码。本文其余内容保留为“恢复包出现前的搜索快照”；
> 当前迁移判断以 `docs/CHANNEL_RECOVERY_MIGRATION_PLAN.md` 为准。

## 1. 结论

本次审计未找到 Telegram、WeCom、WeChat、微信客服或 Hermes 的完整历史实现源码或可独立恢复的部署包。

当前可确认的资产包括：

- Telegram、WeCom、WeChat 的 QwenPaw Channel 配置结构；
- 微信客服（WeCom KF）的运行记录、迁移记录和部分运维脚本；
- Hermes 与 Telegram Bridge 的历史文件名及外部运行路径引用；
- 企业微信和微信公众号相关的运行手册。

这些资产可以用于确认历史架构和恢复配置结构，但不能单独恢复历史 Channel 实现。所有没有实际文件支持的源码、配置或部署脚本均明确标记为 `NOT FOUND`。

## 2. 审计规则

状态含义：

| 状态 | 含义 |
| --- | --- |
| `FOUND` | 找到实际文件，且文件类型与目标一致 |
| `REFERENCE ONLY` | 只找到文件名、路径或运行记录，没有目标文件本体 |
| `PARTIAL` | 找到片段或辅助脚本，但不足以独立恢复能力 |
| `CONFIG ONLY` | 只找到配置结构，不包含实现源码 |
| `NOT FOUND` | 在已完成的扫描范围内没有找到 |

“可恢复”要求至少存在完整源码或可安装扩展包，并具备必要的启动/部署入口。配置模板、运维文档、健康检查脚本和代码片段不单独视为可恢复实现。

扫描过程中未读取或记录 token、secret、credentials、聊天记录、会话内容和数据库内容。

## 3. 扫描范围与限制

### 3.1 已完成

| 范围 | 检查内容 | 结果 |
| --- | --- | --- |
| 当前仓库 | 当前文件、`configs/`、`scripts/`、`drivers/`、`docs/`、`digest/`、历史迁移记录 | 已完成 |
| Git 历史 | 所有可见提交中的文件路径和相关提交说明 | 未发现曾提交的历史 Channel 源码 |
| Workspace 导出包 | `qwenpaw-platform-export.zip` 的完整成员清单及非敏感文本候选 | 未发现 Channel 源码文件或完整部署包 |
| Windows 用户目录 | Desktop、Documents、Downloads、Codex attachments；排除个人微信数据和敏感文件 | 未发现目标源码 |
| `D:\pyprograms` | 精确文件名和候选归档扫描 | 未发现目标源码 |
| 用户主目录 | 对已知历史文件名和备份包名进行精确搜索 | 仅发现桌面导出包副本 |
| 容器候选 | Docker 容器名和卷名 | 未发现 QwenPaw/Channel 候选 |

桌面的 `qwenpaw-platform-export.zip` 与仓库根目录的导出包大小及 SHA-256 完全一致，因此是同一导出包的副本，不是第二份历史备份。

### 3.2 无法完成或不可访问

| 范围 | 状态 |
| --- | --- |
| `/workspace`、`/app`、`/root`、`/opt` | 当前 Windows 主机未暴露这些路径 |
| `\\wsl$`、`\\wsl.localhost` | 未暴露 |
| WSL distribution | 枚举被系统以 `E_ACCESSDENIED` 拒绝，无法检查 Linux 文件系统 |
| D 盘全盘递归扫描 | 精确文件名扫描长时间无返回后限时终止；不能据此断言所有未扫描目录均不存在候选文件 |
| 云端 QwenPaw Runtime 文件系统 | 当前机器未提供挂载或访问入口，未检查 |

因此，本文中的 `NOT FOUND` 表示“在已完成且可访问的扫描范围内未找到”，不表示已检查不可访问的云端 Runtime 或 WSL 文件系统。

## 4. 总体恢复矩阵

| 能力 | 完整源码 | 配置 | 部署/启动脚本 | 可恢复性 |
| --- | --- | --- | --- | --- |
| Telegram | `NOT FOUND` | `FOUND`，但当前禁用 | `NOT FOUND` | `CONFIG ONLY`；历史实现不可恢复 |
| WeCom（QwenPaw Channel） | `NOT FOUND` | `FOUND`，但当前禁用 | `NOT FOUND` | `CONFIG ONLY`；历史实现不可恢复 |
| 微信客服（WeCom KF Gateway） | `NOT FOUND`；仅有少量片段和文件名引用 | 实际运行配置 `NOT FOUND` | `PARTIAL`；有健康检查和清理脚本 | 不可独立恢复 |
| WeChat（QwenPaw Channel） | `NOT FOUND` | `FOUND`，但当前禁用 | `NOT FOUND` | `CONFIG ONLY`；历史实现不可恢复 |
| 微信公众号/机器人 Gateway | `NOT FOUND` | `NOT FOUND` | `NOT FOUND` | `NOT FOUND` |
| Hermes | `NOT FOUND` | `NOT FOUND`；只有外部配置路径引用 | `NOT FOUND`；只有 `start_bridge.sh` 路径引用 | `NOT FOUND` |

## 5. Telegram

| 找到位置 | 文件类型 | 包含源码 | 包含配置 | 包含部署脚本 | 是否可恢复 |
| --- | --- | --- | --- | --- | --- |
| `configs/agent.json` | JSON 配置 | 否 | 是；`channels.telegram` 存在且 `enabled=false` | 否 | `CONFIG ONLY` |
| `qwenpaw-platform-export.zip!/configs/agent.json` | Workspace 导出成员 | 否 | 是；与导入后的配置同源 | 否 | `CONFIG ONLY` |
| `%USERPROFILE%\Desktop\QwenPaw_Hermes_24小时AI_Agent文章.docx` | Word 文档 | 否；只出现 `telegram_bridge.py`、`telegram_bridge_main.py` 文件名，文档内无嵌入源码 | 否 | 否 | `REFERENCE ONLY` |
| 当前仓库、Git 历史、导出包成员、用户目录精确文件名搜索 | 扫描结果 | `telegram_bridge.py`: `NOT FOUND`; `telegram_bridge_main.py`: `NOT FOUND` | — | `NOT FOUND` | 否 |

结论：Telegram 的配置结构存在，但历史 Bridge/Adapter 实现和部署入口均为 `NOT FOUND`。不能从现有资产恢复历史运行实现。

## 6. WeCom

### 6.1 QwenPaw 内置 WeCom Channel

| 找到位置 | 文件类型 | 包含源码 | 包含配置 | 包含部署脚本 | 是否可恢复 |
| --- | --- | --- | --- | --- | --- |
| `configs/agent.json` | JSON 配置 | 否 | 是；`channels.wecom` 存在且 `enabled=false` | 否 | `CONFIG ONLY` |
| `qwenpaw-platform-export.zip!/configs/agent.json` | Workspace 导出成员 | 否 | 是；与导入后的配置同源 | 否 | `CONFIG ONLY` |
| `digest/personal/wecom-production-safety-constraints.md` | 运行约束文档 | 否 | 否 | 否 | `REFERENCE ONLY` |

结论：仓库未包含 QwenPaw Runtime 的 WeCom Channel 实现。配置结构可用于恢复配置形态，不能恢复 Runtime 内置 Channel 源码。

### 6.2 微信客服（WeCom KF Gateway）

| 找到位置 | 文件类型 | 包含源码 | 包含配置 | 包含部署脚本 | 是否可恢复 |
| --- | --- | --- | --- | --- | --- |
| `memory/2026-08-21/wecom-kf-gateway-v34-deployment.md` | 历史部署记录 | 否；记录 `wecom_kf_gateway_v34.py` 至 `v342.py` 等文件名和外部路径 | 否；只引用外部配置 | 否 | `REFERENCE ONLY` |
| `memory/2026-08-21/wecom-kf-v343-deployment.md` | 历史部署记录 | 否；记录 `v342.py`、`v343.py` 文件名 | 否 | 否 | `REFERENCE ONLY` |
| `memory/2026-08-22/wecom-kf-v342-v343-v344-v345-migration.md` | 历史迁移记录 | `PARTIAL`；约 98 行围栏片段，不是任一 Gateway 文件的完整本体 | 否 | 否 | 不可独立恢复 |
| `scripts/healthcheck_v345_final.sh` | Shell 运维脚本 | 否；依赖缺失的 `wecom_kf_gateway_v345.py` | 否 | `PARTIAL`；包含进程启动/健康恢复逻辑 | 不可独立恢复 |
| `scripts/cleanup_old_gateways.sh` | Shell 运维脚本 | 否 | 否 | `PARTIAL`；仅清理和运行态检查 | 不可独立恢复 |
| `digest/procedure/healthcheck-driven-service-auto-recovery.md` | 运维手册 | 否；只引用 Gateway 文件名 | 否 | 否 | `REFERENCE ONLY` |
| `digest/procedure/wecom-gateway-bluegreen-funnel.md` | 运维手册 | 否 | 否 | 否 | `REFERENCE ONLY` |
| `digest/procedure/wecom-gateway-sqlite-migration-and-state-machine.md` | 迁移手册 | 否 | 否 | 否 | `REFERENCE ONLY` |
| `digest/procedure/wecom-image-message-pipeline.md` | 消息链路手册 | 否 | 否 | 否 | `REFERENCE ONLY` |
| `digest/wiki/wecom-kf-api-traps-and-workarounds.md` | API 经验文档 | 否 | 否 | 否 | `REFERENCE ONLY` |
| `/run/.../wecom-kf/wecom_kf_gateway_v34x.py` | 外部运行路径引用 | 文件本体 `NOT FOUND` | — | — | `NOT FOUND` |
| 当前仓库、Git 历史、导出包成员和主机精确文件名搜索 | 扫描结果 | `wecom_kf_gateway_v*.py`: `NOT FOUND` | 实际 Gateway 环境配置：`NOT FOUND` | 完整部署包：`NOT FOUND` | 否 |

端口 `8798` 出现在运维脚本和运行手册中，只能证明历史服务约定，不能替代 Gateway 源码。

结论：可以保留历史运行约束、迁移知识和两份辅助运维脚本；无法从当前资产还原完整的微信客服 Gateway。

## 7. WeChat

### 7.1 QwenPaw 内置 WeChat Channel

| 找到位置 | 文件类型 | 包含源码 | 包含配置 | 包含部署脚本 | 是否可恢复 |
| --- | --- | --- | --- | --- | --- |
| `configs/agent.json` | JSON 配置 | 否 | 是；`channels.wechat` 存在且 `enabled=false` | 否 | `CONFIG ONLY` |
| `qwenpaw-platform-export.zip!/configs/agent.json` | Workspace 导出成员 | 否 | 是；与导入后的配置同源 | 否 | `CONFIG ONLY` |

### 7.2 微信公众号/机器人 Gateway

| 找到位置 | 文件类型 | 包含源码 | 包含配置 | 包含部署脚本 | 是否可恢复 |
| --- | --- | --- | --- | --- | --- |
| `digest/wiki/wechat-mp-48001-passive-reply-bypass.md` | 运行经验文档 | 否 | 否 | 否 | `REFERENCE ONLY` |
| 当前仓库、Git 历史、导出包成员和主机精确文件名搜索 | 扫描结果 | `NOT FOUND` | `NOT FOUND` | `NOT FOUND` | `NOT FOUND` |

结论：内置 WeChat Channel 只保留配置结构；微信公众号/机器人实现只有经验文档，没有实现、配置或部署资产。

## 8. Hermes

| 找到位置 | 文件类型 | 包含源码 | 包含配置 | 包含部署脚本 | 是否可恢复 |
| --- | --- | --- | --- | --- | --- |
| `configs/HEARTBEAT.md` | 健康检查配置文档 | 否 | 否 | 否；仅引用 `/run/.../hermes/start_bridge.sh` | `REFERENCE ONLY` |
| `memory/2026-08-14/wecom-bot-setup.md` | 历史运行记录 | 否；仅引用外部 Hermes 目录和组件名 | 否；只引用外部配置位置 | 否 | `REFERENCE ONLY` |
| `%USERPROFILE%\Desktop\QwenPaw_Hermes_24小时AI_Agent文章.docx` | Word 文档 | 否；没有嵌入源码，只记录 Telegram Bridge 文件名 | 否 | 否 | `REFERENCE ONLY` |
| 当前仓库、Git 历史、导出包成员和主机精确文件名搜索 | 扫描结果 | Hermes 源码：`NOT FOUND` | Hermes 配置文件：`NOT FOUND` | `start_bridge.sh`: `NOT FOUND` | `NOT FOUND` |

结论：Hermes 只存在历史运行痕迹和外部路径引用。源码、实际配置和启动脚本均为 `NOT FOUND`。

## 9. 历史备份判断

| 备份候选 | 判断 |
| --- | --- |
| 仓库根目录 `qwenpaw-platform-export.zip` | Workspace 导出；含配置、文档、memory 和辅助脚本，不含历史 Channel 源码 |
| `%USERPROFILE%\Desktop\qwenpaw-platform-export.zip` | 与仓库导出包 SHA-256 完全一致，是副本，不提供新增恢复内容 |
| 其他 QwenPaw/AgentScope/Channel 备份包 | `NOT FOUND` |

## 10. 后续恢复来源要求

若要继续恢复历史实现，需要从本次不可访问的来源取得实际文件，而不是依据文档重新实现：

1. 云端 QwenPaw workspace 或其 NAS 挂载中的 Hermes、WeCom KF 运行目录；
2. 包含 `telegram_bridge.py`、`telegram_bridge_main.py`、`start_bridge.sh` 或 `wecom_kf_gateway_v*.py` 的原始备份；
3. 云端 Runtime/Extension 发布记录中的原始安装包；
4. 旧主机、旧容器卷或对象存储中的部署制品。

在取得上述实际文件前，各能力的历史实现保持 `NOT FOUND`，不据运行记录推测或重建源码。

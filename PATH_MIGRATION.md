# 绝对路径迁移分析

## 扫描说明

本次扫描覆盖受 Git 管理的文本文件，并单独检查了被忽略的历史 `memory`、`mem_*`、`sessions` 运行记录。历史记录只用于判断云端运行环境，不应批量修改，也不应作为当前源码依赖直接迁移。

本阶段仅记录问题，没有修改任何现有路径。

## 受 Git 管理的路径

| 文件 | 旧路径 | 用途 | 建议替换方式 |
| --- | --- | --- | --- |
| `configs/agent.json` | `/run/csi/mount-root/nas/4079184d856ecc166ed19d4887083405/workspaces/default` | Agent Workspace 根目录 | 由本地 overlay 或环境变量 `QWENPAW_WORKSPACE_DIR` 注入；默认指向项目根目录 |
| `drivers/.legacy_mcp_migration_report.yaml` | 同一 `/run/.../workspaces/default` | 历史 MCP 迁移报告 | 保留报告原值，不作为运行配置读取 |
| `configs/HEARTBEAT.md` | `/run/.../tailscale`、`/run/.../wecom-kf`、`/run/.../hermes` | 云端健康检查入口 | 分别改由 `TAILSCALE_HOME`、`WECOM_GATEWAY_HOME`、`HERMES_HOME` 或服务管理器配置 |
| `scripts/cleanup_old_gateways.sh` | `/run/.../wecom-kf` | 企业微信 Gateway 运维目录 | 未来通过 `WECOM_GATEWAY_HOME` 显式注入，并在脚本启动时校验目录 |
| `scripts/healthcheck_v345_final.sh` | `/run/.../wecom-kf` | 企业微信 Gateway 健康检查 | 同上；本地缺少被检查的 Gateway 实现 |
| `skills/pdf-editor/SKILL.md`、`font-registry/README.txt`、`scripts/pdf_editor.py` | `/app/working/font-registry`、`/app/working/fonts` | PDF 字体注册与搜索目录 | 已有 `PDF_EDITOR_FONT_DIRS` 入口；迁移时把平台默认目录改成基于项目/数据目录的路径，不在本阶段修改 PDF Editor |
| `skills/{docx,pptx,xlsx}/scripts/office/soffice.py` | `C:\Program Files`、`C:\Program Files (x86)` | Windows LibreOffice 发现的默认候选 | 保留为平台候选值，同时优先支持 `SOFFICE_PATH` 或 PATH；这不是项目数据路径 |

受 Git 管理的文件中未发现硬编码 `D:\`、`/root/` 或 `/workspace/` 路径。

## 历史运行态路径

这些路径大量存在于被忽略的会话和 Agent 运行记录中，反映原云端容器布局：

| 旧路径族 | 历史用途 | 建议处理 |
| --- | --- | --- |
| `/app/venv/...` | 云端 Python 虚拟环境与 `qwenpaw` 可执行文件 | 不替换历史记录；新运行时使用当前 venv、`sys.executable` 与 PATH |
| `/app/user-packages/python/...` | 云端用户级 Python 包 | 恢复确切制品后写入 Python lock，不复制绝对路径 |
| `/app/user-packages/node/...` | 云端用户级 Node 包 | 恢复包清单后生成项目级 `package-lock.json` |
| `/app/working/...` | 云端工作目录与中间产物 | 新任务使用 `QWENPAW_DATA_DIR` 或每次任务的临时目录 |
| `/run/.../wecom-kf` | 企业微信/微信客服 Gateway、数据库与脚本 | 作为独立应用恢复后由 `WECOM_GATEWAY_HOME` 指定 |
| `/run/.../hermes` | Telegram/桥接服务运行目录 | 恢复独立组件后由 `HERMES_HOME` 指定 |
| `/root/...`、`/workspace/...` | 容器用户目录或临时 Workspace | 不修改历史记录；新代码使用平台目录解析器或环境变量 |

压缩包二进制中可检出 `C:\`/`D:\` 字符串，但二进制内容不作为可迁移源码证据。

## 建议的路径契约

| 变量 | 责任范围 | 建议默认值 |
| --- | --- | --- |
| `QWENPAW_PROJECT_ROOT` | 只读项目资源 | 从启动文件位置解析，不依赖当前工作目录 |
| `QWENPAW_WORKSPACE_DIR` | Agent 工作区 | 本地默认项目根；生产由部署系统挂载 |
| `QWENPAW_DATA_DIR` | 可变状态、缓存、输出 | Windows 使用 `%LOCALAPPDATA%\qwenpaw-platform`；Linux 遵循 XDG 数据目录 |
| `WECOM_GATEWAY_HOME` | 企业微信 Gateway 独立组件 | 必须显式配置，不猜测 NAS 路径 |
| `HERMES_HOME` | Telegram/Hermes 独立组件 | 必须显式配置 |
| `PDF_EDITOR_FONT_DIRS` | PDF Editor 额外字体目录 | 保留现有环境变量契约 |
| `SOFFICE_PATH` | LibreOffice 可执行文件 | 可选；未设置时再从 PATH/系统安装目录发现 |

实施迁移时应先增加路径解析层和兼容测试，再逐个入口切换；不得批量替换历史记录，也不得一次性改动 PDF Editor、Agent 或 Channel 逻辑。

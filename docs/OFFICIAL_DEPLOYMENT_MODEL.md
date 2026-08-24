# QwenPaw 官方部署、备份与迁移模型

## 文档结论

截至 2026-08-24，官方 QwenPaw Runtime 支持可视化的 Full/Partial Backup，以及 Full/Custom Restore。但这里的“Full”是 **QwenPaw 静态环境数据范围内的完整备份**，不是操作系统、Python 环境、容器镜像、插件依赖和模型权重的整机镜像。

当前 `qwenpaw-platform-export.zip` 应归类为：

> **A. Workspace Backup**

更准确的名称是 **Workspace Export Snapshot**。它不是 Extension Package，也不是 Full Deployment Backup；同时它不符合当前官方 Backup/Restore archive 的 `meta.json + data/...` 格式，因此不能假定可被 Settings → Backup 直接导入。

当前 Git 仓库继续定位为 Extension/Workspace 工程仓库。官方 QwenPaw Runtime 通过 pip、Docker、桌面应用或云端平台独立部署，Git 仓库不复制 Runtime 源码或运行环境。

## 证据等级

| 等级 | 含义 |
| --- | --- |
| 官方确认 | QwenPaw 官方文档或官方 GitHub 仓库明确说明 |
| 本地确认 | 对当前 zip 的文件名和目录结构进行只读检查所得 |
| 尚待实例确认 | 官方产品支持，但 AgentScope Platform 当前租户/版本是否开放该 UI 或 API，公开页面没有作出明确保证 |

## 1. 官方 Backup/Restore 能力

QwenPaw 官方文档提供 Settings → Backup 页面，支持：

- Full backup：全部 Agent workspaces、全局设置、Skill pool 和 Secrets；
- Partial backup：按 Agent 和模块选择，Secrets 默认不选；
- Full restore：用备份中的 Agent workspaces、全局设置、Skill pool、Secrets 完整替换当前实例对应内容；
- Custom restore：只恢复选中的 Agent 或模块，范围外内容保持不变；
- Export/Import：官方 backup zip 可以导出到本地或从本地导入；
- Pre-restore backup：Restore 前可先保存当前状态，便于失败回滚。

官方同时明确：模型权重、Runtime cache 和临时文件不进入 backup。Restore 后需要重启服务使新配置完整生效。详见 [QwenPaw Backup & Restore 官方文档](https://qwenpaw.agentscope.io/docs/backup/) 和对应的 [官方文档源文件](https://github.com/agentscope-ai/QwenPaw/blob/main/website/public/docs/backup.en.md)。

### 云端实例的确认边界

[AgentScope Platform Deploy 页面](https://platform.agentscope.io/deploy) 明确说明配置会保存，并在重新部署时自动恢复；还说明空闲休眠和长期不活跃数据清理规则。但该公开页面没有单独保证每个托管实例、每个版本都开放完整 Backup/Restore UI。

因此结论分两层：

1. **QwenPaw Runtime 产品能力：官方确认支持完整 Backup/Restore。**
2. **当前 AgentScope Platform 租户：尚需在 Console 中确认 Settings → Backup 是否存在，并记录实际 QwenPaw 版本。**

如果云端 Console 没有 Backup 页面，应向 AgentScope Platform 确认版本或托管沙箱限制；不能把“重新部署自动恢复配置”等同于可导出、跨机器恢复的 Full backup。

## 2. 官方 Backup 内容边界

官方 backup zip 最多包含四类内容：

```text
<backup_id>.zip
├── meta.json
└── data/
    ├── config.json
    ├── workspaces/<agent_id>/...
    ├── skill_pool/...
    └── secrets/...
```

| 用户关心的内容 | 官方 Backup | 说明 |
| --- | --- | --- |
| Skills | 是 | Agent workspace 内的 Skills，以及可独立选择的全局 Skill pool |
| Configs | 是 | Agent workspace 内配置和全局 `config.json`；Full backup 均包含 |
| Memory | 是 | Agent workspace 内所有文件包含 memory |
| Sessions/聊天历史 | 是 | Agent workspace 内所有文件包含 chat history/session 数据 |
| Custom files | 是，限定在 Agent workspace 内 | 官方定义为打包所选 Agent workspace 的每个文件 |
| Channel 配置 | 是 | 在 Agent workspace 内；可能包含 `bot_token`、`app_secret` 等敏感字段 |
| LLM/Tool Secrets | Full backup 是；Partial 可选 | 位于独立 Secret 目录；Partial backup 默认不选 |
| 全局 Skill pool | 是 | 是四个独立模块之一 |
| Plugins | **官方未列入** | 已安装插件通常位于工作目录的 `plugins/`，但官方 backup 的四模块与 archive layout 没有 plugins 模块 |
| Plugin Python/npm 依赖 | 否 | 安装到 Runtime 环境的依赖不属于静态 Backup 四模块 |
| MCP 配置 | 条件包含 | 如果配置文件位于 Agent workspace/全局配置中会随文件进入；外部 MCP Server 软件和全局 npm 包不会进入 |
| Runtime 扩展代码 | 条件包含 | 仅当它本身是 workspace 内普通文件；已安装 Plugin、venv、镜像层或系统包不属于官方 Backup |
| QwenPaw/AgentScope Runtime | 否 | 应通过 pip、Docker image、桌面应用或源码安装重建 |
| Local model weights | 否 | 官方要求在目标实例重新下载 |
| Runtime cache/临时文件 | 否 | 官方明确排除 |

### Plugin 的额外说明

官方 Plugin 文档把已安装插件放在类似 `~/.qwenpaw/plugins/<plugin-id>` 的工作目录位置，并使用 `qwenpaw plugin install` 从本地目录或 ZIP/URL 安装。Plugin 可以扩展 Provider、AgentScope Middleware、Hook、命令、HTTP API、前端和 Channel。详见 [QwenPaw Plugin System](https://github.com/agentscope-ai/QwenPaw/blob/main/website/public/docs/plugins.en.md)。

Backup 文档没有把 `plugins/` 列为可选模块，也没有声明会重装插件依赖。因此企业迁移必须把 Plugin 源码包、manifest、依赖 lock 和安装顺序单独版本化，不能只依赖 Full backup。

## 3. 当前导出包判定

对 `qwenpaw-platform-export.zip` 进行只读目录检查，结果为：

- 压缩包大小：5,615,465 bytes；
- 条目数：377；
- 单一顶层目录：`qwenpaw-platform-export/`；
- 包含：`configs/`、`skills/`、`memory/`、`sessions/`、`mem_agent/`、`mem_metadata/`、`mem_session/`、`checkpoints/`、`drivers/`、`scripts/`、`digest/`、README 和迁移说明；
- 不包含：官方 archive 的 `meta.json`、`data/config.json`、`data/workspaces/`、`data/skill_pool/`、`data/secrets/`；
- 不包含：`plugins/`、Runtime 源码、Python venv、Node Runtime 或容器定义；
- 存在 `configs/credentials.yaml` 文件，因此原始 zip 应按敏感归档处理，不得提交 Git、公开分享或作为普通 Extension bundle 发布。

### A/B/C 判定

| 类型 | 是否匹配 | 原因 |
| --- | --- | --- |
| A. Workspace Backup | **是** | 内容是单个 Workspace 的配置、Skills、memory、sessions 和自定义文件快照 |
| B. Extension Package | 否 | 包含大量运行态和私有数据，不是单一 Skill/Plugin/Driver 的可发布包 |
| C. Full Deployment Backup | 否 | 没有 Runtime、依赖环境、Plugin、官方全局设置/Secret archive layout 和部署镜像 |

这一定义是内容分类，不代表它是当前官方 Backup Import 可识别的 zip。官方 Import 应使用 QwenPaw 自身生成、含 `meta.json` 的 backup archive。

## 4. 官方部署模式

官方 [Quick Start](https://github.com/agentscope-ai/QwenPaw/blob/main/website/public/docs/quickstart.en.md) 列出 pip、安装脚本、Docker、AgentScope Platform、Alibaba Cloud ECS、ModelScope Studio 和 Desktop App 等模式。

### pip 模式

官方要求 Python 3.11–3.13，基本流程为：

```text
pip install qwenpaw
qwenpaw init --defaults
qwenpaw app
```

Console 默认位于 `http://127.0.0.1:8088/`。pip 模式适合需要控制 Python 环境的本地开发或单机部署，但 Workspace、Secret 和 Backup 目录仍应与 Git 源码分离。

### Docker 模式

官方镜像为 `agentscope/qwenpaw`，稳定 tag 为 `latest`，预发布 tag 为 `pre`。官方示例使用三个独立持久卷：

```text
qwenpaw-data     → /app/working
qwenpaw-secrets  → /app/working.secret
qwenpaw-backups  → /app/working.backups
```

三个卷分别保存配置/memory/Skills、模型与工具 Secrets、backup archives。未挂载 backup volume 时，容器重建会丢失容器内备份。生产环境应固定经过验证的版本或 image digest，而不是把可变 `latest` 当作可复现基线。

### 源码开发模式

官方 Runtime 源码开发流程是独立 clone [agentscope-ai/QwenPaw](https://github.com/agentscope-ai/QwenPaw)：

1. 在 `console/` 执行 `npm ci` 和前端 build；
2. 将 build 结果复制到 `src/qwenpaw/console/`；
3. 使用 `pip install -e .`，开发依赖使用 `pip install -e ".[dev,full]"`；
4. 执行 `qwenpaw init --defaults` 和 `qwenpaw app`；
5. 官方 CLI 支持 `qwenpaw app --reload` 用于开发时自动重载，详见 [CLI 文档](https://github.com/agentscope-ai/QwenPaw/blob/main/website/public/docs/cli.en.md)。

这个模式用于贡献或调试 QwenPaw Runtime，应在独立官方源码 checkout 中进行，不应把 Runtime 源码复制进当前 Extension/Workspace 仓库。

## 5. 云端模式

### AgentScope Platform

- 无需本地安装，通过浏览器一键部署；
- 官方 Quick Start 表明平台提供稳定版和 Beta 版体验；
- Deploy 页面表明配置会在重新部署时自动恢复；
- 平台可能有休眠和长期不活跃数据清理策略，因此不能把平台持久化当作唯一灾备；
- 应定期使用 QwenPaw 官方 Backup/Export（如果当前实例开放）导出独立归档。

### 自管云主机/ECS

企业可以在 ECS/VM 上使用 pip、Docker 或官方一键部署。自管模式允许固定 Runtime 版本、控制磁盘、网络、Secret、backup volume 和对象存储生命周期，适合生产环境。

云端与本地可以通过 **官方 backup archive** 迁移 Workspace 静态环境；Runtime 和未被 backup 覆盖的 Plugin/依赖仍要在目标环境单独重建。

## 6. 本地模式如何结合当前 Workspace

### 不建议

- 不要把当前 Git 仓库直接当作 `QWENPAW_WORKING_DIR`；Runtime 会写入会话、memory、缓存和配置，容易污染源码仓库。
- 不要把 `qwenpaw-platform-export.zip` 直接上传到官方 Backup Import；它缺少官方 metadata/layout。
- 不要从 zip 中复制 `credentials.yaml` 到 Git 或开发 fixture。
- 不要用本地自制 Loader 模拟 Cloud Runtime，然后声称迁移成功。

### 推荐流程

1. 在当前云端 Console 记录 QwenPaw 版本，并确认 Settings → Backup 是否可用。
2. 在云端创建官方 Full backup 用于灾备；另创建最小 Partial backup 用于特定 Agent 迁移。两者都按 Secret 资产保存，因为 Agent workspace 可能包含 Channel 凭据。
3. 本地使用固定版本的官方 pip 包或 Docker image 创建干净 Runtime。
4. 为本地 Runtime 使用独立工作目录/volume、独立 Secret 目录和独立 backup 目录。
5. 通过官方 Backup Import 导入官方 archive；不要手工伪造 `meta.json`。
6. 从当前 Git 仓库以官方 Skill/Plugin/MCP 安装机制同步正在开发的 Extension，不覆盖整个 Runtime 目录。
7. 在 Console 验证 Agent、Skills、memory、sessions 和 Channel 配置；外部 Channel 默认保持禁用并使用测试凭据。

如果当前云端不提供官方 Backup 页面，应保留现有 Workspace export 作为只读取证快照，同时向平台确认受支持的导出/恢复路径；在得到答案前，不执行破坏性格式转换。

## 7. 企业扩展模式

企业扩展建议分成四类制品：

| 制品 | 存储位置 | 发布/恢复方式 |
| --- | --- | --- |
| QwenPaw Runtime | 官方 pip 版本或固定 Docker image digest | 从官方制品重新安装/拉取 |
| Skills/MCP/Workspace 非敏感资产 | 当前 Git 仓库 | Review、CI、版本化 bundle、官方安装机制 |
| Plugins/Runtime 扩展 | 独立 Plugin package 或企业自定义 image | `qwenpaw plugin install` 或构建固定基础镜像；单独记录依赖 |
| Runtime 数据与 Secrets | Data/Secret/Backup volume 或加密对象存储 | 官方 Backup/Restore；严格访问控制，不进入 Git |

企业自定义 Docker image 可以从官方 image 继承，用于安装经过审查的系统/Python 依赖。Workspace data、Secrets 和 backups 继续用独立 volume，不烘焙进镜像。

Plugin 能修改 Middleware、Hook、HTTP API、前端和 Channel，属于高权限 Runtime 扩展。它与普通 Skill 的风险等级不同，必须有 manifest、QwenPaw 兼容版本、依赖 lock、安全评审、staging 测试和独立回滚包。

## 8. 当前项目推荐架构

```text
                    ┌──────────────────────────────┐
                    │ Official QwenPaw Runtime     │
                    │ pip / pinned Docker image   │
                    └──────────────┬───────────────┘
                                   │ consumes
                    ┌──────────────▼───────────────┐
                    │ qwenpaw-platform Git repo    │
                    │ Skills / Config templates    │
                    │ MCP Drivers / Plugin source  │
                    │ Tests / Docs / Runbooks      │
                    └──────────────┬───────────────┘
                                   │ writes runtime state
          ┌────────────────────────┼────────────────────────┐
          ▼                        ▼                        ▼
  Workspace/Data volume     Secret volume/store      Backup volume/store
  configs/memory/sessions    provider/channel keys    official backup zip
```

架构原则：

- Runtime 与 Extension 源码分离；
- Runtime 版本和 Extension commit 同时记录；
- Git 不是 Backup，Backup 也不是源代码管理；
- Workspace export 用于取证和迁移辅助，官方 backup archive 用于支持范围内的 Restore；
- Plugins 和 Runtime 依赖单独打包，不假定 Full backup 能恢复；
- Secrets 永不进入 Git；
- 生产部署优先固定版本/镜像 digest，并保留异地加密 backup；
- 恢复演练必须覆盖 Runtime 重建、官方 Restore、Plugin 重装和外部服务重连四个步骤。

## 9. 当前迁移边界

| 当前资产 | 后续处理 |
| --- | --- |
| Git 中的 Skills/Configs/Drivers/Docs | 继续工程化维护，不包含 Runtime |
| 原始 `qwenpaw-platform-export.zip` | 保持 ignored、加密归档；视为 Workspace snapshot，不作为发布包 |
| Cloud Workspace | 优先从当前 Runtime 重新生成官方 Full/Partial backup |
| QwenPaw Runtime | 选择并固定官方 pip/Docker 版本，独立安装 |
| Plugins/Runtime 扩展 | 从原环境另行盘点、打包和验证；当前 zip 未包含 |
| Memory/Sessions | 通过官方 backup 或受支持的 Workspace restore 迁移，不进入 Git |
| Credentials | 使用 Secret store/Secret volume；当前 zip 按敏感资产管控 |

本阶段只明确模型和边界，不修改 Agent、Streaming、Channel、PDF 或任何 Runtime/业务代码。

## 官方来源

- [QwenPaw Backup & Restore](https://qwenpaw.agentscope.io/docs/backup/)
- [Backup 文档源文件](https://github.com/agentscope-ai/QwenPaw/blob/main/website/public/docs/backup.en.md)
- [QwenPaw Quick Start](https://github.com/agentscope-ai/QwenPaw/blob/main/website/public/docs/quickstart.en.md)
- [QwenPaw CLI](https://github.com/agentscope-ai/QwenPaw/blob/main/website/public/docs/cli.en.md)
- [QwenPaw Plugin System](https://github.com/agentscope-ai/QwenPaw/blob/main/website/public/docs/plugins.en.md)
- [QwenPaw Config & Working Directory](https://qwenpaw.agentscope.io/docs/config/)
- [AgentScope Platform Deploy](https://platform.agentscope.io/deploy)
- [QwenPaw 官方 GitHub 仓库](https://github.com/agentscope-ai/QwenPaw)

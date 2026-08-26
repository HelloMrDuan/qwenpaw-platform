# QwenPaw Platform 能力矩阵

> Channel strategy update: Telegram、企业微信和微信在 QwenPaw v2.1.0 中为
> `BUILTIN`，生产默认使用内置 Channel。历史 Telegram/WeCom Adapter、Plugin
> 与 Bridge 为 `LEGACY / FALLBACK / REFERENCE ONLY`。微信客服是独立的
> `CUSTOM / TO VERIFY` 链路。详见 `QWENPAW_CHANNEL_STRATEGY.md`。

## 1. 文档目的

本矩阵记录 `qwenpaw-platform` 当前可证明的能力、Extension 类型、入口、配置、依赖和测试状态，并区分：

- 已有能力：导出 Workspace 中存在配置、源码、脚本或云端运行证据；
- 未来规划：目标架构或 Roadmap 已提出，但当前没有可发布实现；
- Runtime 能力：由 QwenPaw/AgentScope Cloud Runtime 提供，不属于当前 Git 仓库源码。

本矩阵不以“目录存在”等同于“当前可运行”，也不以“历史上运行过”等同于“已在本仓库完成工程化”。

## 2. 状态定义

| 状态 | 定义 |
| --- | --- |
| 已运行 | 有云端会话、runbook、运维入口或用户确认的实际运行证据；标记“云端历史”时不代表当前本地可运行 |
| 已配置 | `configs/agent.json`、`configs/skill.json` 或 Driver 中存在可识别配置/注册项 |
| 未启用 | 配置存在，但 `enabled=false`；不得在未验证凭据和外部服务前启用 |
| 待开发 | 没有仓库内可发布实现，或现有云端实现源码未导出、需要恢复后工程化 |

同一能力可以同时具有多个状态，例如“已运行（云端历史）＋未启用＋待开发（源码恢复）”。

## 3. 类型定义

| 类型 | 在本矩阵中的含义 |
| --- | --- |
| Channel | 面向用户的消息收发渠道 |
| Plugin | 注册 Runtime/Channel/Provider、管理连接与生命周期的高权限扩展 |
| Adapter | Channel payload、附件、身份、响应和错误的纯转换层 |
| Skill | Agent 可选择并执行的用户任务或工作流 |
| MCP | 通过 Model Context Protocol 暴露的外部工具 |

一个能力可能有主类型和配套类型。例如 Telegram 是 Channel，工程实现通常由 Channel Plugin 和消息 Adapter 组成。

## 4. 当前已集成能力

### 4.1 Channel、Gateway 与外部集成

| 能力 | 类型判断 | 当前状态 | 入口位置 | 配置位置 | 主要依赖 | 测试状态 | 归属 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Console | Channel | 已运行（云端历史）；已配置、当前启用 | 官方 QwenPaw Runtime；仓库无独立入口 | `configs/agent.json` → `channels.console` | QwenPaw/AgentScope Runtime、模型 Provider | 有 `sessions/console/` 历史运行数据；本地 Runtime 未安装，未做当前冒烟 | 已有能力 |
| Hermes | Plugin + Adapter（外部桥接服务） | `TO VERIFY`；保留历史运行证据 | 恢复源码与历史启动资料 | 与历史 Channel Bridge 相关；生产角色未确认 | Hermes Runtime、模型/网络 | 有离线历史验证；独立生产必要性未证明 | 已有历史能力，待决策 |
| Telegram | Channel（QwenPaw builtin） | `BUILTIN`；生产默认 | QwenPaw v2.1.0 内置 Channel | Runtime Console：Bot Token、代理、Typing、访问控制等 | QwenPaw Runtime、Telegram API | 内置能力由真实 Console 确认；历史 Adapter/Plugin 测试仅作参考 | 已有 Runtime 能力 |
| 企业微信机器人 | Channel（QwenPaw builtin） | `BUILTIN`；生产默认 | QwenPaw v2.1.0 内置企业微信 Channel | Runtime Console：Bot ID、Secret、扫码授权、媒体目录、群聊上下文 | QwenPaw Runtime、企业微信服务 | 内置能力由真实 Console 确认；历史 Adapter/Plugin 测试仅作参考 | 已有 Runtime 能力 |
| 企业微信客服 Gateway | Plugin + Adapter + Channel Gateway | `CUSTOM / TO VERIFY` | `plugins/wechat-customer/`、`adapters/wechat_customer/` 与历史 Gateway | `open_kfid`、`external_userid`、cursor、Gateway-owned DB | 企业微信客服 API、SQLite、Gateway、QwenPaw | 离线链路测试已存在；与内置微信等价性未证明 | 已有历史能力，待决策 |
| 微信 | Channel（QwenPaw builtin） | `BUILTIN`；生产默认 | QwenPaw v2.1.0 内置微信 Channel | Runtime Console 扫码登录 / Bot Token 配置 | QwenPaw Runtime、微信服务 | 内置入口由真实 Console 确认；需 staging 配置验收 | 已有 Runtime 能力 |
| 企业微信图片生成链路 | Plugin/Gateway 内嵌能力；目标应拆为 Skill 或 MCP + Adapter | 已运行（云端历史）；待开发（独立 Extension） | 外部 `sn_agent_runner.py` 与 WeCom Gateway；仓库仅有 `digest/procedure/wecom-image-message-pipeline.md` | 外部环境变量与 Gateway 配置，未作为平台 Extension 导出 | 图片生成 Provider、图片压缩、企业微信 media/upload、SQLite、QwenPaw | 历史 runbook 记录压缩、上传、状态机和失败回退验收；无源代码测试 | 已有链路；独立能力属未来规划 |

### 4.2 已注册 Skills

以下 17 个 Skill 均在 `configs/skill.json` 中 `enabled=true`、`channels=["all"]`。其中 16 个来源为 `builtin` 导出快照，`pdf-editor` 来源为 `customized`。

| 能力 | 类型 | 当前状态 | 入口位置 | 配置位置 | 主要依赖 | 测试状态 | 归属 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `QA_source_index` | Skill | 已配置 | `skills/QA_source_index/SKILL.md` | `configs/skill.json` | QwenPaw Skill Loader、知识源索引能力 | 未发现专属自动化测试 | 已有能力（builtin 快照） |
| `browser` | Skill | 已配置 | `skills/browser/SKILL.md` | `configs/skill.json` | QwenPaw Browser/浏览器工具、可用浏览器环境 | 未发现专属自动化测试 | 已有能力（builtin 快照） |
| `channel_message` | Skill | 已配置 | `skills/channel_message/SKILL.md` | `configs/skill.json` | QwenPaw Channel Runtime、目标 session/channel 与凭据 | 未发现专属自动化测试 | 已有能力（builtin 快照） |
| `chat_with_agent` | Skill | 已配置 | `skills/chat_with_agent/SKILL.md` | `configs/skill.json` | QwenPaw Multi-Agent/CLI 或 API、目标 Agent | 未发现专属自动化测试 | 已有能力（builtin 快照） |
| `cron` | Skill | 已配置 | `skills/cron/SKILL.md` | `configs/skill.json` | QwenPaw Scheduler、jobs 配置、Runtime 常驻进程 | 未发现专属自动化测试 | 已有能力（builtin 快照） |
| `dingtalk_channel` | Skill | 已配置 | `skills/dingtalk_channel/SKILL.md` | `configs/skill.json` | DingTalk API/凭据、QwenPaw Channel 配置 | 未发现专属自动化测试 | 已有能力（builtin 快照） |
| `docx` | Skill | 已配置 | `skills/docx/SKILL.md`、`skills/docx/scripts/` | `configs/skill.json` | Python 文档/XML 库、LibreOffice、Poppler；部分流程使用 Node `docx` | 有脚本级验证工具；未发现专属 `tests/` | 已有能力（builtin 快照） |
| `file_reader` | Skill | 已配置 | `skills/file_reader/SKILL.md` | `configs/skill.json` | QwenPaw 文件工具、Workspace 文件访问 | 未发现专属自动化测试 | 已有能力（builtin 快照） |
| `guidance` | Skill | 已配置 | `skills/guidance/SKILL.md` | `configs/skill.json` | QwenPaw Runtime/Agent 指令加载 | 未发现专属自动化测试 | 已有能力（builtin 快照） |
| `himalaya` | Skill | 已配置 | `skills/himalaya/SKILL.md` | `configs/skill.json` | `himalaya` 可执行文件、邮件账号/网络 | 注册表声明 `require_bins: himalaya`；未发现专属测试 | 已有能力（builtin 快照） |
| `make-skill` | Skill | 已配置 | `skills/make-skill/SKILL.md` | `configs/skill.json` | QwenPaw Skill/文件工具 | 未发现专属自动化测试 | 已有能力（builtin 快照） |
| `make_plan` | Skill | 已配置 | `skills/make_plan/SKILL.md` | `configs/skill.json` | QwenPaw Agent/计划能力 | 未发现专属自动化测试 | 已有能力（builtin 快照） |
| `multi_agent_collaboration` | Skill | 已配置 | `skills/multi_agent_collaboration/SKILL.md` | `configs/skill.json` | QwenPaw Multi-Agent、Agent 通信入口 | 未发现专属自动化测试 | 已有能力（builtin 快照） |
| `pdf` | Skill | 已配置 | `skills/pdf/SKILL.md`、`skills/pdf/scripts/` | `configs/skill.json` | pypdf、pdfplumber、pdf2image、Pillow、Poppler；OCR 时需要 Tesseract | 有工具脚本；未发现专属 `tests/` | 已有能力（builtin 快照） |
| `pdf-editor` | Skill | 已运行（云端历史）；已配置、当前注册启用 | `skills/pdf-editor/SKILL.md` → `skills/pdf-editor/scripts/pdf_editor.py` | `configs/skill.json` | PyMuPDF、pypdf、pdf2image/pdfplumber、Pillow、字体目录/fontconfig、Poppler | 有 `skills/pdf-editor/tests/regression_suite.py` 和 QA 报告；当前本地依赖未安装，本轮未执行 | 已有能力（customized） |
| `pptx` | Skill | 已配置 | `skills/pptx/SKILL.md`、`skills/pptx/scripts/` | `configs/skill.json` | LibreOffice、Poppler/pdf2image、PptxGenJS/Node 和 OOXML 工具 | 有脚本级检查/渲染流程；未发现专属 `tests/` | 已有能力（builtin 快照） |
| `xlsx` | Skill | 已配置 | `skills/xlsx/SKILL.md`、`skills/xlsx/scripts/` | `configs/skill.json` | openpyxl、LibreOffice 重算、可选 Git/redlining | 有脚本级重算/验证流程；未发现专属 `tests/` | 已有能力（builtin 快照） |

“已配置”只证明 Skill 已注册启用，不证明当前本地环境具备 QwenPaw Runtime、系统二进制和全部依赖，也不证明所有 Skill 已做端到端测试。

### 4.3 MCP 与外部工具

| 能力 | 类型 | 当前状态 | 入口位置 | 配置位置 | 主要依赖 | 测试状态 | 归属 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Tavily Search | MCP | 已配置；未启用 | `drivers/mcp/tavily_search.yaml`；stdio 命令 `npx -y tavily-mcp@latest` | `configs/agent.json` → `mcp.clients.tavily_search`、Driver YAML、ignored credential store | Node/npx、`tavily-mcp`、Tavily API、`TAVILY_API_KEY`、网络 | `digest/procedure/mcp-subprocess-credential-staleness.md` 有运维故障经验；无仓库内协议/集成测试，版本未锁定 | 已有能力，待生产化 |
| Built-in Tools（shell/file/code/image view） | Runtime Tool | 已配置 | 官方 QwenPaw Runtime；实现不在仓库 | `configs/agent.json` → `tools.builtin_tools` | QwenPaw Runtime、OS 权限与安全策略 | 当前仓库没有 Runtime Tool 测试；属于官方 Runtime 验收范围 | 已有 Runtime 能力，不属于 Extension 源码 |

## 5. 未来规划能力

| 能力 | 目标类型 | 当前状态 | 计划入口位置 | 计划配置位置 | 计划依赖 | 当前测试状态 | 归属 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 统一消息模型 | Adapter/Core Contract | 待开发 | 未来 `adapters/message-normalization/` 或平台契约目录 | versioned message schema | JSON Schema/Pydantic 等待实现时选定 | 无实现、无 fixture；Roadmap Phase 2 | 未来规划 |
| Console 标准 Adapter | Adapter | 待开发 | 未来 `adapters/console/` | Console capability/config overlay | 官方 QwenPaw Console Channel | 无实现；应作为统一消息模型参考测试 | 未来规划 |
| Telegram 自定义 Plugin/Adapter | Plugin + Adapter + Channel | `STOPPED`；仅保留 legacy/fallback/reference | 现有恢复目录不再扩展为生产 Channel | 不新增生产配置 | 内置 Telegram Channel | 离线历史测试保留；不新增 BaseChannel 测试 | 非未来规划 |
| 企业微信自定义 Plugin/Adapter | Plugin + Adapter + Channel | `STOPPED`；仅保留 legacy/fallback/reference | 现有恢复目录不再扩展为生产 Channel | 不新增生产配置 | 内置企业微信 Channel | 离线历史测试保留；不新增 BaseChannel 测试 | 非未来规划 |
| 微信客服能力核验 | Custom Channel/Gateway decision | `TO VERIFY` | `plugins/wechat-customer/`、`adapters/wechat_customer/` | 只记录 secret 名称与 Gateway 状态边界 | open-kfid API、cursor、DB、去重 | 先核验内置覆盖与回滚语义，不开发新功能 | 待架构决策 |
| 统一 Response Streaming | Adapter/Core Contract | 待开发 | 未来 response event/Channel renderer 适配层 | stream capability 与 fallback schema | QwenPaw Runtime event boundary、各 Channel 能力 | 无实现；Roadmap Phase 3 | 未来规划 |
| OCR 独立能力 | Skill，必要时组合 MCP/Provider Adapter | 待开发 | 未来 `skills/ocr/` | Skill 注册 + OCR Provider/语言包配置 | Tesseract 或云 OCR、Poppler、语言模型/版面分析 | 通用 PDF 文档有 OCR 说明，但无独立 Skill、schema 或基准集 | 未来规划 |
| 独立图片生成 | Skill + MCP 或 Provider Plugin + Artifact Adapter | 待开发 | 未来 `skills/image-generation/`，可配 `mcp/`/`plugins/` | Provider credential reference、模型/尺寸策略 | 图片生成 Provider、存储、内容安全、Channel artifact 支持 | 只有企业微信历史内嵌链路；无独立实现测试 | 未来规划 |
| 视频生成 | Skill + MCP/Provider Plugin + Artifact Adapter | 待开发 | 未来 `skills/video-generation/` | 异步 job、Provider、存储、费用/审批配置 | 视频 Provider、对象存储、轮询/回调、转码 | 无实现、无测试 | 未来规划 |
| MCP 目录标准化 | MCP | 待开发 | 未来 `mcp/<mcp-id>/` | `mcp.yaml` + Runtime 兼容 Driver | 精确 Server 版本、transport、Secret reference | 当前只有 Tavily Driver，无统一测试 | 未来工程化 |
| Extension 统一测试门禁 | 跨类型测试能力 | 待开发 | `tests/` + 各 Extension `tests/` | CI/Cloud staging 配置 | 固定 Runtime、脱敏 fixture、测试租户 | `tests/README.md` 只有规范，尚无平台测试 harness | 未来规划 |

## 6. 能力归属汇总

### 已有能力

- Cloud Runtime 与 Console；
- Hermes 外部桥接能力；
- Telegram、企业微信机器人、企业微信客服、微信机器人/公众号历史运行链路；
- 17 个已注册 Skill；
- Customized PDF Editor；
- Tavily MCP 配置；
- shell、file、code、image view 等 Runtime Built-in Tools；
- 企业微信图片生成历史链路。

其中 Hermes 和外部 Channel/Gateway 属于“能力已有、源码未导出”；恢复源码、版本和测试是工程化工作，不应将其误标为全新业务需求。

### 未来规划

- 统一消息模型与 Channel Adapters；
- 统一 Response Streaming；
- Telegram、企业微信、微信使用内置 Channel；不再规划重复的生产 Plugin/Adapter；
- 微信客服独立能力核验与架构决策；
- 独立 OCR、图片生成和视频生成能力；
- MCP 标准目录与版本锁定；
- Extension 自动化测试门禁和 Cloud staging 验收。

Word、Excel、PPT 并非“完全不存在”：仓库已经有 `docx`、`xlsx`、`pptx` builtin Skill 快照并已注册。它们的未来工作是依赖可复现、补充测试、版本化和 Cloud staging 验证，而不是从零创建重复 Skill。

## 7. 当前关键缺口

1. Hermes 的独立生产角色、微信客服与内置微信的能力边界仍未完成验证。
2. `channels/` 没有实现，`plugins/`、`adapters/`、`mcp/` 目标目录尚未进入渐进迁移。
3. 除 PDF Editor 回归脚本外，现有 Skills 普遍没有专属测试目录。
4. Tavily MCP 使用 `@latest` 且未启用，不满足生产版本锁定要求。
5. 本地缺少已固定版本的 QwenPaw Runtime，无法完成当前端到端运行验证。
6. 历史 runbook 是运行证据和恢复输入，不是可发布源码或自动化测试的替代品。

本矩阵只记录现状，不授权修改 PDF、Agent、Streaming、Channel 或 Runtime 代码。

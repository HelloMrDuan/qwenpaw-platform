# 平台扩展点

## 扩展原则

新增能力优先作为 Skill 或外部 Tool Driver 接入，复用 QwenPaw Cloud Runtime 的 Agent、Tool Router、Channel 和会话能力。只有出现稳定且跨多个 Skill 的契约需求时，才在 `core/` 增加薄适配层；不得为单个能力修改 Agent 或重写 Runtime。

当前没有独立 `extensions/` 目录。现阶段的逻辑扩展面是：

- `skills/`：用户可感知的领域能力；
- `drivers/`：MCP 或外部 Provider 的进程/连接声明；
- `configs/`：启用状态、非敏感参数和凭据引用；
- `tests/`：跨 Skill/Tool 的契约测试；
- `docs/`：开发、发布、限制和运行手册；
- 未来 `channels/`：只处理消息与制品传输，不承载生成逻辑。

## 通用变更位置

| 变更类型 | 应修改位置 | 不应修改位置 |
| --- | --- | --- |
| 新领域操作 | `skills/<skill>/` | Agent、Channel、Streaming 内部 |
| 外部 SaaS/模型 Provider | `drivers/mcp/` 或 Skill 的 provider adapter | `configs/agent.json` 中硬编码 SDK 逻辑 |
| Python 依赖 | Skill 文档与 `requirements.lock.txt` | 云端全局 site-packages 路径 |
| Node 依赖 | 归属明确的未来 `package.json`/lock | 全局 npm 安装 |
| 非敏感配置 | `configs/` 示例/overlay 或 Driver YAML | Skill 源码常量 |
| 凭据 | 本地 ignored 文件、Cloud Secret/credential reference | Git、日志、fixture |
| 回归测试 | Skill 自身 `tests/` 与平台 `tests/skills/` | 生产历史会话直接复制 |
| 制品发送 | Runtime artifact 结果 + Channel Adapter | Skill 直接调用 Telegram/微信 API |

## 能力映射

### PDF

当前入口：`skills/pdf/` 与 `skills/pdf-editor/`。

- 通用读取、创建、合并、拆分、表单和 OCR 辅助流程归 `skills/pdf/`。
- 确定性实际编辑归 `skills/pdf-editor/`。
- PDF Editor 在专门迁移计划和完整回归/视觉验收前保持不变。
- 新 PDF 操作先判断应扩展现有 Skill 还是成为独立能力，避免再创建重叠 Skill。

### Word

当前入口：`skills/docx/`。

- Word 创建、读取、编辑、批注、修订和渲染验证在该目录扩展。
- 新增操作时补充 `SKILL.md` 契约、对应脚本、脱敏 fixture 和渲染验证。
- LibreOffice、Pandoc 等系统依赖必须在发布记录中声明，不写死安装路径。

### Excel

当前入口：`skills/xlsx/`。

- 表格读写、公式、样式、图表和重算能力在该目录扩展。
- 公式结果必须经过 LibreOffice 等受支持引擎重算和验证。
- 输入/输出以文件制品为边界，不让 Channel 传输细节进入 Skill。

### PPT

当前入口：`skills/pptx/`。

- 演示文稿生成、读取、编辑、缩略图和渲染验证在该目录扩展。
- 版式/视觉回归应同时检查结构化内容和页面渲染。
- Provider 素材搜索或图片生成通过 Tool/Skill 组合，不直接耦合到 PPT 执行器。

### OCR

建议新入口：未来 `skills/ocr/`，作为独立、可选的重依赖能力。

- 输入：图片或 PDF artifact。
- 输出：结构化文本块、置信度、页码/坐标，以及可选 searchable PDF artifact。
- 本地 Provider（如 Tesseract）与云端 OCR Provider 通过统一 provider interface 隔离。
- `skills/pdf/` 可以编排 OCR；`pdf-editor` 不承担 OCR 重绘引擎，除非另立专项计划。
- 依赖、语言包、页数/大小限制、网络权限和数据驻留必须进入 manifest/README 与测试。

### 图片生成

建议新入口：未来 `skills/image-generation/`；Provider 接入放在 Skill adapter 或 `drivers/`。

- 输入：prompt、尺寸、宽高比、可选参考图和安全策略。
- 输出：图片 artifact、MIME、尺寸、Provider job id 和安全的生成元数据。
- 凭据只通过 credential reference 注入。
- Channel 只负责上传/发送 artifact；企业微信 Gateway 不应包含图片生成业务逻辑。
- 失败、内容策略、超时和重试应返回结构化结果，不把 Provider 原始错误直接发送用户。

当前导出包没有独立图片生成 Skill；历史 runbook 中的图片调用链不能替代版本化 Skill 源码。

### 视频生成

建议新入口：未来 `skills/video-generation/`，并采用异步 job 契约。

- 提交阶段返回 job id；轮询/回调阶段更新进度；完成后返回视频、封面和元数据 artifact。
- 大文件放入 Runtime/对象存储管理的 artifact storage，不写入 Git 或会话 JSON。
- 明确最大时长、分辨率、超时、取消、费用确认、内容策略和过期时间。
- Channel 不支持大文件或长连接时，采用最终链接/通知等能力降级；降级逻辑属于 Channel Adapter。

## 新 Skill 的目标结构

当前 17 个 Skill 仍以 `SKILL.md` 为兼容入口。新能力采用已定义的目标结构，但发布前必须确认 Cloud Runtime 是否识别新增 manifest；不识别时保留 `SKILL.md` 作为实际入口：

```text
skills/<name>/
├── SKILL.md
├── skill.yaml
├── schemas/
├── executor/
├── tests/
└── README.md
```

`skill.yaml` 是仓库目标契约，不代表当前 Cloud Runtime 已原生支持。兼容 Loader 未被导出，因此不能将 manifest 支持写成现状事实。

## 注册与发布触点

一个新能力通常涉及：

1. `skills/<name>/`：实现、说明、schema、测试和制品契约。
2. `configs/skill.json`：Cloud Runtime 安装/导出后形成的注册状态；优先由官方安装流程生成，不手工猜测内部字段。
3. `requirements.lock.txt` 或未来 Node lock：精确依赖。
4. `drivers/`：需要 MCP/外部进程时添加。
5. 未来的 `configs/credentials.example.yaml`（当前不存在）：只声明凭据名称和用途，不包含值；创建需作为独立配置基线变更审查。
6. `tests/`：跨 Runtime 边界的契约 fixture。
7. `docs/`：限制、发布、回滚和运维说明。

## 不需要触碰的区域

新增上述能力默认不修改：

- QwenPaw/AgentScope Agent 核心；
- Planner 或 Tool Router 内部算法；
- Streaming 实现；
- Telegram、企业微信、微信 Channel；
- `memory/`、`sessions/` 与其他历史运行态数据；
- PDF Editor（除非能力本身是经批准的 PDF Editor 专项变更）。

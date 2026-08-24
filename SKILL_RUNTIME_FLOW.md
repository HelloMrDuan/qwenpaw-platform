# Skill Runtime 执行链路

## 当前链路

```text
用户输入
  ↓
Channel 接收（当前只有 Console 启用）
  ↓
QwenPaw Cloud Runtime 创建/恢复会话
  ↓
Agent / AgentScope 进行推理
  ↓
Runtime 暴露已启用 Skill 的元数据与说明
  ↓
Agent 选择 Skill，并遵循该 Skill 的 SKILL.md
  ↓
Runtime Tool Router 调用 shell / file / code / MCP 等工具
  ↓
Skill 脚本或外部工具执行，产生结构化结果和文件制品
  ↓
Runtime 将工具结果交回 Agent
  ↓
Agent 组织最终回答
  ↓
Runtime 通过 Channel 流式或聚合返回用户
```

仓库能够确认 Skill 注册、说明、脚本和制品契约；无法确认 Cloud Runtime 内部的 Skill 排序算法、Prompt 拼装方式、工具调度实现和 Streaming 事件实现。

## 分阶段责任

| 阶段 | 当前所有者 | 仓库输入 | 仓库输出/影响 |
| --- | --- | --- | --- |
| 用户输入与会话 | Cloud Runtime / Channel | `configs/agent.json` Channel 配置 | 原始消息进入 Agent 会话 |
| Agent 推理 | QwenPaw / AgentScope | Agent、模型、工具和安全配置 | 产生回答或工具/Skill 调用意图 |
| Skill 候选发现 | Cloud Runtime | `configs/skill.json` 的 enabled、channels、description、source | 向 Agent 暴露候选能力 |
| Skill 选择 | Agent + Runtime | 用户意图、文件类型、Skill 描述 | 选中一个或多个 Skill；算法未导出 |
| Skill 指令加载 | Cloud Runtime | `skills/<name>/SKILL.md` | 形成执行步骤和约束 |
| Skill 执行 | Runtime Tool Router + Skill 资产 | Skill 脚本、依赖、输入文件和 scoped workspace | stdout/stderr、结构化结果、制品文件 |
| 结果处理 | Agent + Runtime | 工具结果、错误、进度和制品引用 | 用户可读回答或后续工具调用 |
| 返回 Channel | Cloud Runtime / Channel | 最终文本、制品、可能的事件 | Console/外部 Channel 消息 |

## Skill 选择依据

当前可验证的选择输入包括：

- `configs/skill.json` 中的 `enabled` 与 `channels`；
- Skill 元数据中的名称与 description；
- `SKILL.md` frontmatter 的 description 和正文触发规则；
- 用户消息中的文件类型、动作和交付物要求。

仓库中 17 个 Skill 均为 enabled。`pdf`、`docx`、`pptx`、`xlsx` 与 `pdf-editor` 均声明对 `all` Channel 可用。实际选择优先级由 Cloud Runtime/Agent 决定，仓库中不存在可审计的选择器代码。

## PDF Editor 接入位置

PDF Editor 接入在 **Skill 选择之后、工具执行阶段**：

```text
用户要求修改 PDF
  ↓
Agent 在 pdf / pdf-editor 等候选 Skill 中作出选择
  ↓
加载 skills/pdf-editor/SKILL.md
  ↓
先执行 info 分类与定位
  ↓
通过 Runtime shell/code 工具调用 scripts/pdf_editor.py
  ↓
输出新 PDF、校验结果和结构化 JSON
  ↓
Runtime 将结果返回 Agent，再由 Channel 交付
```

已确认的 PDF Editor 契约：

- 注册名为 `pdf-editor`，enabled，适用于 `all` Channel。
- 来源为 `customized`，安装来源记录为 zip。
- 实际 PDF 修改必须调用 `skills/pdf-editor/scripts/pdf_editor.py`。
- 源 PDF 不得覆盖；默认生成新文件。
- 进度模式通过 `PDF_EDITOR_PROGRESS=1` 开启，JSONL 写入 stderr，最终 JSON 保留在 stdout。
- 结果必须经过该 Skill 定义的校验后才可交付。

因此 PDF Editor 不是 Channel Adapter，也不是 AgentScope 内部模块；它是由 Runtime 选择和调度的 Workspace Skill。

## PDF 与 PDF Editor 的重叠

`pdf` 的 description 覆盖读取、创建、合并、拆分、表单、OCR 和编辑等广泛任务；`pdf-editor` 则强调确定性实际修改、范围定位、视觉校验与进度事件。两者存在触发范围重叠。

当前仓库无法证明 Runtime 如何消解重叠。现阶段应保留两者，不修改优先级；后续可先通过 Cloud staging 记录真实选择案例，再决定是否只调整元数据描述。任何 PDF Editor 变更仍需独立回归计划。

## 现有 Skill 的两种执行形态

### 指令型 Skill

部分 Skill 主要提供操作说明，由 Agent 组合 Runtime 内置工具、命令行程序或短代码完成任务。例如 `pdf`、`docx`、`pptx`、`xlsx` 的 `SKILL.md` 会指导 Agent 使用各自 `scripts/`、Python 库、LibreOffice 或 Poppler。

### 封装执行型 Skill

`pdf-editor` 将核心修改集中在单一脚本入口，具有更明确的命令、进度、事务性和验证契约。

当前没有统一的 `skill.yaml`/executor ABI。未来标准化应先包裹现有入口并做行为对比，不要求 Runtime 改造或 Skill 重写。

## 失败和返回边界

- Skill 脚本负责输入校验、文件安全、领域错误和制品完整性。
- Runtime 负责进程生命周期、工具权限、超时/取消、结果采集以及把结果送回 Agent。
- Agent 负责决定重试、继续调用工具或生成用户可读响应。
- Channel 只负责传输和能力降级，不解释 PDF/Office 领域错误。

由于 Runtime 源码缺失，现有超时、取消、stderr 解析和错误脱敏是否覆盖所有 Skill 尚需在 Cloud staging 中实测。

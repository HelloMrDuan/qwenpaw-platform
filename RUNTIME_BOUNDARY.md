# QwenPaw Runtime 边界

## 结论

当前 Git 仓库是 **QwenPaw Workspace 与扩展资产的工程仓库**，不是 QwenPaw Cloud Runtime 的源码仓库或可独立运行的 Runtime 分发包。

仓库负责保存、评审、测试和发布 Runtime 所消费的 Skills、非敏感配置、外部工具驱动、适配层设计及工程文档。Agent 循环、Planner、Skill Loader、Tool Router、Channel Runtime、Streaming Engine 等执行能力仍由 QwenPaw Cloud Runtime / AgentScope 提供。

本边界不要求重写、复制或替代 QwenPaw Runtime。

## 仓库拥有的内容

| 责任域 | 当前证据 | 当前状态 | 仓库责任 |
| --- | --- | --- | --- |
| Skills | `skills/`、`configs/skill.json` | 17 个导出 Skill；其中 16 个标记为 `builtin`，`pdf-editor` 标记为 `customized` | 自定义 Skill 的工程源；内置 Skill 的兼容快照、依赖说明和测试基线 |
| Configs | `configs/agent.json`、`configs/skill.json`、`configs/.mcp` | 云端 Workspace 的版本化非敏感配置快照 | 配置审查、示例、兼容性和敏感字段留空 |
| Extensions | `drivers/mcp/`、Skill 内脚本、`scripts/` | Tavily MCP Driver、Office/PDF 工具脚本、外部 Gateway 运维脚本 | 外部能力声明、驱动配置、运维契约；不拥有外部服务本身 |
| Adapters | `apps/`、`core/`、`channels/` | 当前仅占位，没有适配器实现 | 未来可放置 Runtime 边界适配器和 Channel 适配器，但必须渐进引入 |
| Documentation | `docs/`、`digest/`、根目录工程文档 | 架构、状态、迁移、启动与生产 runbook | 工程决策、运行证据、开发和发布规范 |
| Tests | `tests/`、部分 Skill 自带测试 | 只有测试规范和少量 Skill 回归资产 | 本地契约、离线执行、制品与 Cloud staging 验收 |

`memory/`、`sessions/`、`mem_*`、`checkpoints/` 是保留在本地的 Runtime 状态或历史数据，不是 Runtime 源码，也不是版本化产品代码。

`source=builtin` 表示这些 Skill 的上游所有权仍可能属于 QwenPaw Runtime/发行包。Git 中存在其导出内容，只能证明仓库保存了兼容快照，不能证明可以绕过官方扩展机制直接覆盖云端内置版本。自定义修改应先确认官方 override/安装语义；`pdf-editor` 是当前唯一明确标记为 `customized` 的 Skill。

## 不属于当前仓库的 Runtime 能力

| Runtime 能力 | 仓库内证据 | 边界结论 |
| --- | --- | --- |
| Agent 主循环与迭代控制 | 只有 `configs/agent.json` 参数，没有实现源码 | Cloud Runtime 所有 |
| AgentScope 推理与模型调用 | 有 backend/model 配置，没有 AgentScope 包或源码 | QwenPaw/AgentScope Runtime 所有 |
| Planner 实现 | 架构文档只描述逻辑位置 | 未导出，不由当前仓库实现 |
| Skill 发现、描述注入和选择器 | 有 Skill 注册表与 `SKILL.md`，没有 Loader/Selector 源码 | Cloud Runtime 所有 |
| Tool Router 与权限执行 | 有 builtin tool/MCP 配置，没有 Router 源码 | Cloud Runtime 所有 |
| Channel 生命周期 | 有 Channel 配置，`channels/` 无实现 | Cloud Runtime 或未导出的外部 Gateway 所有 |
| 统一 Streaming Engine | 有配置字段和目标设计，没有实现 | Cloud Runtime 当前行为；本仓库只可定义未来边界契约 |
| Runtime 持久化实现 | 有运行态目录和参数，没有存储引擎源码 | Cloud Runtime 所有 |
| QwenPaw CLI/API Server | 文档引用 `qwenpaw` 命令，没有可执行文件或包清单 | 外部 Runtime 分发物 |

## 共享契约面

仓库与 Cloud Runtime 通过文件和进程契约协作：

```text
Git repository                         QwenPaw Cloud Runtime
──────────────────────────────────     ─────────────────────────────
configs/agent.json                 ──▶  Agent 与 Channel 配置加载
configs/skill.json                 ──▶  Skill 注册状态与元数据
skills/*/SKILL.md                  ──▶  Skill 触发和操作说明
skills/*/scripts                   ──▶  Runtime 工具执行的脚本/制品逻辑
drivers/mcp/*.yaml                 ──▶  MCP 子进程声明与凭据引用
非敏感版本化资产                  ◀──  Runtime 兼容性和加载约束
```

共享契约不意味着仓库拥有 Runtime 内部实现。Runtime 可以升级内部算法，但应保持经过验证的配置、Skill、工具结果和错误契约兼容。

## 事实等级

### 已确认

- 当前唯一启用的 Channel 是 Console。
- `configs/skill.json` 注册了 17 个启用的 Skill。
- `pdf-editor` 对所有 Channel 可用，来源为 `customized`，安装来源记录为 zip。
- 当前 Skill 采用 `SKILL.md`；仓库中没有 `skill.yaml`。
- QwenPaw CLI、AgentScope 包、Skill Loader、Tool Router 和 Channel 源码不在 Git 仓库。
- Tavily MCP 使用 stdio/npx 声明，当前禁用。

### 根据配置和 Skill 契约推断

- Runtime 根据注册表和 Skill 描述向 Agent 暴露可用能力。
- Agent 选中 Skill 后读取/遵循 `SKILL.md`，再通过 Runtime 提供的 shell、文件或代码工具执行 Skill 脚本。
- Runtime 收集工具结果并交回 Agent，最终由 Channel 返回用户。

这些推断符合现有配置和历史行为，但选择器算法、Prompt 拼装、重试、错误映射和事件解析的具体实现无法由当前仓库证明。

## 变更准入规则

- Skill 行为变化只进入对应 `skills/<name>/`，不得修改 Runtime 来适配单个 Skill。
- Runtime 配置变化只进入版本化非敏感配置或本地 overlay；凭据不得进入 Git。
- MCP/外部服务通过 `drivers/` 和凭据引用接入，不把 Provider SDK 写进 Agent 逻辑。
- Channel 传输变化只进入未来的 `channels/<channel>/` 适配器，不进入 Skill。
- `core/` 只允许保存平台自有契约和对 Runtime 公共接口的薄适配器，不复制 AgentScope 内部代码。
- 无法判断属于哪一侧时，先记录接口证据，不以重写 Runtime 作为默认方案。

## 边界验收

满足以下条件才可声称某项扩展被本仓库支持：

1. 版本化源文件、依赖和测试均在仓库责任范围内。
2. 不依赖未记录的云端绝对路径或全局包。
3. 在本地隔离模式完成 Skill/Driver 验证。
4. 在非生产 Cloud Workspace 完成 Runtime 集成验证。
5. 发布和回滚均不要求修改或替换 QwenPaw Runtime。

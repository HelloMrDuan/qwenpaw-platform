# 本地开发模式

## 目标

本地仓库用于开发和验证 Workspace 扩展，不模拟、重写或替代 QwenPaw Cloud Runtime。开发闭环分为“本地隔离验证”和“Cloud staging 集成验证”；只有后者能够证明 Skill 被真实 Runtime 正确发现、选择和返回。

## 四层开发模型

```text
Git branch / worktree
  ↓
本地 Skill 隔离执行
  ↓
本地契约与制品验证
  ↓
QwenPaw Cloud staging Workspace 集成
  ↓
版本化发布到目标 Workspace
```

| 层级 | 是否需要 QwenPaw Runtime | 验证内容 |
| --- | --- | --- |
| L0 静态检查 | 否 | Skill 目录、frontmatter/manifest、依赖、路径和敏感信息 |
| L1 隔离执行 | 否 | 脚本/执行器输入输出、错误、超时、文件安全 |
| L2 制品验证 | 否 | PDF/Office/OCR/图片/视频的结构与渲染质量 |
| L3 Runtime 集成 | 是，使用 Cloud staging | Skill 发现、选择、工具调度、结果回传和权限 |
| L4 Channel 验收 | 是，使用测试 Channel/租户 | 文本、artifact、能力降级、重试和幂等 |

本地可以完成 L0-L2；L3-L4 不能用自制 Runtime 代替。

## 开发 Skill

1. 从 `main` 创建短生命周期分支或独立 worktree。
2. 选择现有 `skills/<name>/`，或为新能力创建独立目录；不批量移动其他 Skill。修改 `source=builtin` 的 Skill 前必须先确认 Cloud Runtime 的官方 override/安装机制，避免本地快照被升级覆盖。
3. 先记录现有触发描述、输入、输出、依赖、错误和 artifact 行为。
4. 为变更添加最小脱敏 fixture 和失败用例。
5. 修改 `SKILL.md`、脚本/执行器、schema 和 README 中真正属于该能力的部分。
6. 精确锁定新增依赖，禁止依赖云端全局安装或绝对路径。
7. 保持 Channel 无关：Skill 返回文本、结构化结果和 artifact，不直接发送外部消息。

现有 Skill 没有统一 executor ABI，开发者必须以其 `SKILL.md` 和实际脚本入口为准。目标 `skill.yaml` 只能渐进加入，且不得假定 Cloud Runtime 已原生支持。

## 测试 Skill

### 静态与安全测试

- Skill 名称、description、触发范围和依赖完整。
- 路径限定在测试 workspace；不得覆盖源文件或越界写入。
- fixture、日志和错误信息不含 token、secret、用户私有内容或云端绝对路径。
- 外部网络默认关闭；Provider 调用使用 fake/stub。

### 隔离执行测试

- 直接运行 Skill 声明的脚本/执行器，而不是启动本地替代 Runtime。
- 覆盖正常输入、非法输入、缺失依赖、取消/超时和重复执行。
- stdout、stderr、退出码和 artifact 必须符合 Skill 文档。
- PDF Editor 继续使用其现有入口和回归资产；未经专项批准不修改测试对象代码。

### 制品测试

- PDF：结构、页数、文本/对象变化和页面渲染。
- DOCX/PPTX/XLSX：OOXML 结构、可打开性、内容与 LibreOffice 渲染/重算。
- OCR：文本、坐标、置信度和多语言基准。
- 图片/视频：MIME、尺寸、时长、编码、大小和可解码性。

### Cloud staging 测试

- 使用非生产 Workspace 和测试凭据。
- 验证 Skill 是否被发现、何时触发、实际调用哪个脚本、制品如何返回。
- 记录 Runtime 版本、配置快照、输入 fixture、结果摘要和 trace id。
- 外部 Channel 默认不启用；需要验收时使用测试 bot/租户。

## 发布 Skill

当前仓库没有可验证的 QwenPaw Skill 发布 CLI 或 API，因此发布命令必须从 Cloud Runtime 官方流程或原部署制品中恢复，不能在文档中猜测。对 `source=builtin` 的 Skill，应发布为官方支持的 override/customized 形态或提交给上游；不得直接替换 Runtime 自带目录。

发布包至少包含：

- 完整 Skill 目录；
- 版本号和变更说明；
- 依赖 lock/系统依赖清单；
- 输入输出及 artifact 契约；
- 测试结果摘要；
- 文件清单与 SHA-256；
- 兼容的 QwenPaw/AgentScope Runtime 版本记录；
- 回滚版本和回滚步骤。

建议发布流程：

1. 合并前完成 L0-L2，并审查 Git diff 范围。
2. 构建不可变 Skill bundle，记录 commit id 与 SHA-256。
3. 通过已验证的官方安装/导入机制发布到 Cloud staging。
4. 完成 L3；需要时完成 L4。
5. 创建 Git tag 或 release 记录，将同一 bundle 提升到目标 Workspace。
6. 从 Runtime 重新导出非敏感注册状态并核对 `configs/skill.json`；不手工伪造安装字段。

## 回滚

回滚单位是单个 Skill bundle，不是整个 Runtime。

1. 发布前保留当前生产 bundle、配置快照、commit id 和校验和。
2. 新旧版本至少跨一个观察窗口并存，不在首次发布时删除旧版本。
3. 回滚时通过相同的官方安装机制恢复上一不可变 bundle。
4. 核对 Skill 注册状态、依赖、触发描述和 artifact 行为。
5. 在 Cloud staging 重放最小 fixture，再恢复生产流量/启用状态。
6. 不删除或回写 `memory/`、`sessions/`、`mem_*`、`checkpoints/`。

如果 Skill 产生持久化数据，新版本必须优先采用向后兼容格式；不可逆迁移必须独立审批、备份并提供数据回滚方案。

## 分支与版本策略

- 一个分支只处理一个 Skill 或一个 Driver。
- 使用语义化版本描述 Skill 契约变化；Runtime 兼容范围单独记录。
- 发布制品绑定 Git commit，不从未提交工作区构建。
- `main` 保存可发布的 Workspace 状态；生产是否启用仍由 Cloud Runtime 配置决定。
- 紧急修复从当前生产 tag/commit 分支，验证后再合回 `main`。

## 完成定义

一个 Skill 变更只有同时满足以下条件才算可发布：

- 本地可在干净环境安装其已锁定依赖。
- L0-L2 全部通过，没有真实凭据和私有 fixture。
- Cloud staging 已证明 Runtime 能发现、选择、执行并返回结果。
- 目标 Channel 的 artifact 能力或降级行为已验证。
- bundle、commit、校验和、兼容 Runtime 版本和回滚版本均有记录。
- 发布不要求修改、复制或替换 QwenPaw/AgentScope Runtime。

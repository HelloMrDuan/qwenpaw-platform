# 测试基线

本目录先定义测试边界和分层，不在平台运行时尚未恢复时编写大量猜测性测试。

## 测试原则

- 默认离线、可重复、无真实外部凭据。
- fixture 必须脱敏，不直接读取或复制 `memory/`、`mem_*`、`sessions/` 中的生产历史数据。
- 单元测试不访问 Telegram、企业微信、微信、Tavily 或模型服务。
- 集成测试通过显式标记和环境变量启用，默认测试命令不得产生外部消息或修改生产状态。
- 先为现状建立契约，再进行目录迁移或行为改造。

## 测试分层

### Agent 测试

- 配置 schema 与必填字段校验。
- Planner、Tool Router、错误边界的契约测试。
- 多轮 session 隔离与 memory 结构兼容性。
- 模型调用使用 stub/fake，验证超时、取消和错误脱敏。

建议位置：`tests/agent/`。

### Skill 测试

- 每个 Skill 的元数据、输入 schema、输出 schema 和 executor 契约。
- 临时目录内的真实小样本测试；输出文件做结构和渲染双重验收。
- 缺少 LibreOffice、Poppler、Tesseract 等外部二进制时给出明确 skip/diagnostic，不静默通过。
- PDF Editor 保留现有回归脚本，本阶段不改其逻辑。

建议位置：Skill 自身的 `tests/` 放专属测试，`tests/skills/` 放跨 Skill 契约测试。

### Tool 调用测试

- Tool Registry、参数校验、权限策略与超时。
- MCP stdio 生命周期、JSON-RPC 错误映射、进程退出与凭据脱敏。
- 外部 Tool 使用 fake server；真实 Tavily 测试仅在受控 CI job 中运行。

建议位置：`tests/tools/`。

### Streaming 测试

- chunk 顺序、增量合并、结束信号、取消和背压。
- Tool call 与文本 chunk 的边界。
- Channel 能力降级：不支持流式的渠道应得到确定性的聚合响应。
- 网络断开、重连、重复事件和超时下的幂等性。

建议位置：`tests/streaming/`。

## 后续测试入口

待 QwenPaw/AgentScope 运行时和依赖来源恢复后，再选择并锁定测试框架，统一为一个本地命令和一个 CI 命令。目前仓库没有可验证的 pytest/unittest 项目入口，因此本阶段不虚构命令。

最小验收顺序应为：配置静态校验 → Console 冒烟 → Skill 契约 → Tool fake 集成 → Streaming 契约 → 测试租户 Channel 集成。

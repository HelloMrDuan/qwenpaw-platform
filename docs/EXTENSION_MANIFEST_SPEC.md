# Extension Manifest Specification

状态：Phase 5.2 基线。本文定义 Extension 仓库中的 Plugin/Adapter 描述协议，不是 QwenPaw Runtime 的安装器实现。

## 1. 文件位置与解析规则

每个 Plugin 或 Adapter 根目录必须包含 `manifest.yaml`：

```text
plugins/<name>/manifest.yaml
adapters/<name>/manifest.yaml
```

Schema 位于 `schemas/extension-manifest.schema.json`。路径字段相对包含 Manifest 的扩展根目录解析，禁止绝对路径和 `..` 路径逃逸。

当前仓库没有锁定 YAML 解析依赖。为保证本地基线仅依赖 Python 标准库，Phase 5.2 的 Manifest 使用 **JSON-compatible YAML 1.2 profile**：文件是合法 YAML 1.2，同时可以由 JSON parser 离线校验。后续若引入锁定版本的 YAML parser，可以扩展书写形式，但不得改变字段语义。

## 2. 字段定义

| 字段 | 类型 | 约束与语义 |
| --- | --- | --- |
| `name` | string | 小写 kebab-case；应与扩展目录名一致 |
| `type` | string | 只能为 `plugin` 或 `adapter`；并须与父目录类型一致 |
| `version` | string | Extension 包版本，采用 SemVer；`-recovered` 表示恢复基线，不等于上游源码版本 |
| `description` | string | 当前能力、来源状态和边界的简述 |
| `runtime` | string | 主入口运行时，只能为 `python` 或 `node` |
| `entrypoint` | relative path | 相对扩展根目录的现存主入口；描述入口，不授权自动执行 |
| `dependencies` | string[] | 已确认的语言、包、系统或外部依赖；恢复版本未知时必须明确标注 |
| `config_template` | relative path/null | 脱敏配置模板；`null` 表示当前恢复资产没有模板，不能自动配置 |
| `healthcheck` | object/null | 标准健康检查；对象含 `type` (`http`/`command`) 与 `target`；`null` 表示尚未标准化 |
| `ports` | integer[] | 扩展监听端口；无监听或无法确认时为空列表，不记录第三方远端端口 |
| `required_secrets` | string[] | 启动时无条件需要的 secret 标识符；只记录名称，严禁记录值 |

`required_secrets` 为空不表示扩展永远不需要凭证。例如 Hermes 支持多个模型 Provider，没有单一、无条件必需的 secret，具体 Provider 的 secret 由配置阶段决定。

## 3. 当前恢复基线的特殊约束

- `config_template: null` 是可审计的缺失状态，不得自动生成带猜测字段的模板。
- `healthcheck: null` 表示没有满足标准的只读健康检查。
- 历史 `healthcheck_v345.sh` 带有自动拉起进程的副作用，因此 Manifest 使用其真实只读 HTTP `/healthz` 接口，而不是把该脚本登记为健康检查。
- WeCom 源码允许 `SENSENOVA_API_KEY` 作为 `SN_API_KEY` 的历史别名；Manifest 记录标准注入名 `SN_API_KEY`。
- Manifest 只描述恢复入口，不消除源码中的历史绝对路径，也不代表组件已经 `READY_FOR_DEPLOYMENT`。

## 4. 生命周期

### install

1. 校验 Manifest 格式、Schema、目录类型及路径边界。
2. 验证入口存在并检查依赖是否能按锁定版本解析。
3. 从不可变 Release Package 安装源码；不复制 secret、日志、数据库、PID 或 session 状态。
4. 恢复基线若依赖或入口不完整，安装流程必须停止并报告缺口。

### configure

1. 若 `config_template` 非空，以模板创建环境专属配置副本。
2. 通过部署环境的 secret provider 注入 `required_secrets`，不得写回 Git。
3. `config_template: null` 的组件必须先补充并审核脱敏模板，不能猜测生成生产配置。
4. 配置校验与 Runtime 注册是部署层职责，不在 Manifest 解析阶段执行。

### start

1. 确认安装版本、配置和依赖校验均通过。
2. 由部署包装层按 `runtime` 启动 `entrypoint`。
3. Manifest 本身不得 import、执行或修改恢复源码。
4. 当前五个 `-recovered` 版本仅供描述和审计，不能据此直接判定可启动。

### healthcheck

1. `http` 检查访问 `target` 并要求成功响应；`command` 检查执行相对扩展目录的只读命令。
2. 健康检查不得启动、停止、重启或修改服务状态。
3. `healthcheck: null` 时，部署系统应报告 `UNAVAILABLE`，不能把进程存在等同于健康。

### upgrade

1. 新扩展版本使用新的不可变 Release Package 和独立 Manifest 版本。
2. 在 staging 完成 Schema、依赖、配置、启动和健康检查验证。
3. 备份允许迁移的配置与持久状态；secret 仍由环境注入。
4. 切换版本后保留前一制品，禁止原地覆盖恢复源码。

### rollback

1. 停止失败版本并恢复上一已验证 Release Package。
2. 恢复与旧版本兼容的配置/状态快照，重新注入 secret。
3. 执行上一版本健康检查并记录回滚结果。
4. 回滚部署制品，不通过修改 Git 历史或临时改 Gateway 代码完成。

## 5. Runtime 边界

Manifest 是 Extension 仓库的静态发布元数据。它不替代 AgentScope/QwenPaw Runtime 的扩展发现、进程管理、Channel 注册、消息协议或 Streaming 实现。Runtime 接入前仍须完成适配包装、配置模板、依赖锁、staging 验收和正式发布审批。

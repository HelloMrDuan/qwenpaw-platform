# Skill Extension Model

状态：Phase 5.4 统一发现基线。本文定义 Skill 如何进入 Extension Registry，同时保留 QwenPaw 现有 Skill 兼容入口。

## 1. Skill 与其他扩展的区别

| 类型 | 核心职责 | 典型生命周期 | 是否长期监听 | 主要契约 |
| --- | --- | --- | --- | --- |
| Skill | 完成一次文件处理、AI 能力或工具任务 | validate → invoke → result | 否 | request/result Schema、Artifact、StreamEvent |
| Plugin | 增强 Runtime 或集成外部服务 | install → configure → start → healthcheck → stop | 通常是 | 进程入口、配置、端口、健康检查、secret |
| Adapter | 转换 Channel/外部协议与平台协议 | configure → connect → parse/render → disconnect | 取决于协议 | 消息/协议映射、传输入口 |

Skill 是可调用能力，不是常驻服务。它不应通过端口或进程存活状态表达可用性；其可用性来自 Manifest、输入/输出 Schema、执行器路径和离线测试均通过验证。

## 2. 双描述文件兼容

标准化 Skill 可以同时保留：

```text
skills/<skill>/
├── SKILL.md       # QwenPaw 当前发现与使用说明
├── skill.yaml     # 已有 Skill/Contract 描述，保持兼容
└── manifest.yaml  # Extension Registry 静态发现描述
```

`manifest.yaml` 不替代、不生成也不修改 `SKILL.md` 或 `skill.yaml`。Registry 只读取 `manifest.yaml`；QwenPaw Runtime 是否读取其他文件仍由 Runtime 自身决定。

## 3. Skill Manifest 字段

Skill 与 Plugin/Adapter 共享：

- `name`：全局唯一的 kebab-case 名称，并与目录名一致；
- `type`：固定为 `skill`；
- `version`：Skill Extension 的 SemVer；
- `description`：能力及边界摘要；
- `dependencies`：已确认的语言与执行依赖，只描述，不自动安装。

Skill 专属字段：

### executor

```json
{
  "runtime": "python",
  "path": "executor/main.py",
  "callable": "execute"
}
```

- `runtime` 只能是当前规范支持的 `python` 或 `node`；
- `path` 必须是 Skill 根目录内现存的相对文件；
- `callable` 是未来调用包装层使用的符号名称；Loader 不 import 或解析该符号。

### schemas

```json
{
  "request": "schemas/request.schema.json",
  "result": "schemas/result.schema.json"
}
```

两个路径必须存在。Loader 只确认路径，不在发现阶段执行请求/结果业务校验。

### artifacts

`inputs` 和 `outputs` 分别声明 Artifact 的名称、类型、允许 MIME type 以及是否必需；`uri_scheme` 当前固定为 `artifact`。Manifest 只声明 Contract 边界，不读取、复制或上传真实文件。

### events

声明 Skill 可能产生的标准 StreamEvent 子集。允许值来自统一 Streaming Contract；声明事件不代表 Loader 会订阅或消费事件。

### tests

列出相对 Skill 根目录的现存测试文件，用于发布前验证范围。Registry 不自动运行它们。

## 4. PDF Editor V1.2 映射

PDF Editor 的 Extension Manifest 映射如下：

- 执行器：`executor/main.py` → `execute`；
- Schema：`schemas/request.schema.json`、`schemas/result.schema.json`；
- 输入 Artifact：必需 PDF，以及可选 PDF/图片操作资源；
- 输出 Artifact：`artifact://` 下的 `application/pdf`；
- 事件：`tool.start`、`tool.progress`、`file.created`、`tool.result`、`tool.error`；
- 测试：Contract、回归和视觉验收测试文件。

这些内容来自现有 V1.2 Contract，不改变 `scripts/pdf_editor.py` 或 `executor/main.py`。

## 5. Registry 投影

为了保持统一查询，Loader 把 Skill 字段投影为 `ExtensionMetadata`：

```text
executor.runtime → runtime
executor.path    → entrypoint
dependencies     → dependencies
healthcheck      → None
```

同时保留 `executor`、`schemas`、`artifacts`、`events` 和 `tests` 作为 Skill 专属元数据。Plugin/Adapter 不能携带这些字段，Skill 也不能伪装成带端口、secret 或 healthcheck 的常驻扩展。

## 6. 执行边界

当前 Loader/Registry 只完成：读取、字段校验、目录类型校验、路径存在性校验、静态查询。它不会：

- import `executor`；
- 调用 `callable`；
- 解析真实 Artifact；
- 执行 PDF 操作；
- 发布 StreamEvent；
- 注册到 AgentScope/QwenPaw Runtime。

未来真实 Skill 调用必须经过独立的 Runtime 集成/Tool Router 层，并继续使用现有 `SkillRequest`、`SkillResult`、Artifact 和 StreamEvent Contract。

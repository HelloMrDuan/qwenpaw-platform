# Extension Runtime Model

状态：Phase 5.3 静态发现基线。本文描述本地 Extension Registry 与 AgentScope/QwenPaw Runtime 的边界。

## 1. 当前执行链路

```text
Git workspace
    │
    ├── plugins/*/manifest.yaml
    ├── adapters/*/manifest.yaml
    └── skills/*/manifest.yaml
            │
            ▼
    ExtensionLoader
    - 解析 Manifest
    - 校验 Schema 字段
    - 校验目录类型
    - 校验声明路径
            │
            ▼
    ExtensionMetadata
    - name / type / version
    - runtime / entrypoint
    - healthcheck / dependencies
            │
            ▼
    ExtensionRegistry
    - register / discover
    - get / list
            │
            ▼
    静态查询结果
```

链路在静态查询结果处终止。`entrypoint` 是描述字段，不会被 import、spawn 或执行。

## 2. 发现范围

Registry 只检查仓库根下三类目录的直接子目录：

- `plugins/<extension>/manifest.yaml`；
- `adapters/<extension>/manifest.yaml`；
- `skills/<extension>/manifest.yaml`。

它不会递归进入 `recovered/`，因此 Hermes 上游源码内部的 MCP Manifest 不会污染平台 Registry。

默认发现模式兼容当前渐进迁移：缺少 Manifest 的旧目录被跳过。严格模式 `discover(strict=True)` 用于迁移审计，会在注册前汇总并拒绝缺失 Manifest 的目录。

当前仓库有 5 个可发现扩展：4 个 Plugin 和 1 个 Adapter。历史 Skill 尚未完成 Extension Manifest 标准化；现有 `SKILL.md` 或 `skill.yaml` 不会被猜测转换，也不会被当前 Registry 注册。Phase 5.2 Schema 仍只允许 `plugin`/`adapter`，未来 Skill Manifest 必须先独立定义并升级 Schema。

## 3. Loader 验证边界

Loader 离线验证：

- YAML 1.2 JSON-compatible profile 可解析；
- 必填字段存在且没有未知字段；
- `type`、`runtime`、版本、名称、端口和 secret 标识合法；
- Manifest 类型与 `plugins/`、`adapters/`、`skills/` 目录一致；
- `entrypoint`、非空 `config_template` 和 command healthcheck 是扩展目录内的现存文件；
- HTTP healthcheck 是结构合法的 URL。

Loader 不验证外部依赖已经安装、secret 值存在、远程 API 可达或入口能够成功运行。这些属于 staging/部署验收。

## 4. Registry 语义

- 名称在 Plugin、Adapter、未来 Skill 之间全局唯一。
- `register()` 拒绝重复名称，不覆盖已有元数据。
- `discover()` 先完成整批解析及重名检查，再写入 Registry，避免明显的部分注册。
- `get(name)` 不存在时返回 `None`。
- `list()` 返回按名称排序的不可变快照，并支持按类型过滤。
- Registry 是进程内只读目录，不是数据库、服务管理器或 Runtime 状态中心。

## 5. 与 QwenPaw Runtime 的边界

| 能力 | Extension Registry | AgentScope/QwenPaw Runtime 或未来部署层 |
| --- | --- | --- |
| 扫描 Git 中的 Manifest | 是 | 可消费结果 |
| Schema 与本地路径验证 | 是 | 可进行二次发布验证 |
| import/启动入口 | 否 | 部署包装层审核后负责 |
| Plugin/Channel 注册 | 否 | Runtime 集成层负责 |
| Agent/会话/消息路由 | 否 | Runtime 负责 |
| Streaming 消费 | 否 | Runtime/Extension Streaming Bridge 负责 |
| secret 读取与注入 | 否 | 部署环境 secret provider 负责 |
| 健康探测执行 | 否 | 部署/编排层负责 |
| 升级与回滚 | 否 | Release/部署流程负责 |

## 6. 后续接入门槛

在 Registry 元数据进入真实 Runtime 之前，仍需完成：

1. 为目标扩展补齐依赖锁与脱敏配置模板。
2. 为 Skill 定义与现有 `skill.yaml`/`SKILL.md` 兼容的 Manifest 规范。
3. 实现独立部署包装层，显式把静态 Metadata 转换为 Runtime 注册请求。
4. 在 Cloud staging 验证安装、配置、启动、健康检查和停止。
5. 以不可变 Release Package 发布，并保留上一版本用于回滚。

任何后续启动能力都应位于新的部署/Runtime 集成模块中，不能加入当前 Loader 或 Registry。

# Extension Registry and Loader

该目录提供 Extension 层的本地静态发现能力，不属于 QwenPaw Runtime。

```text
plugins/*/manifest.yaml  ─┐
adapters/*/manifest.yaml ─┼─> ExtensionLoader ─> ExtensionMetadata ─> ExtensionRegistry
skills/*/manifest.yaml   ─┘
```

## 职责

- `models.py`：不可执行的 `ExtensionMetadata`、扩展类型和主运行时枚举。
- `loader.py`：读取 JSON-compatible YAML 1.2 Manifest，按仓库 Schema、目录类型和本地路径进行验证。
- `registry.py`：扫描一级扩展目录、检测全局重名并提供 `register()`、`discover()`、`get()`、`list()`。

## 使用方式

```python
from pathlib import Path

from core.extensions import ExtensionRegistry

registry = ExtensionRegistry(Path.cwd())
registry.discover()
telegram = registry.get("telegram")
plugins = registry.list("plugin")
```

`discover()` 默认兼容历史目录：没有 `manifest.yaml` 的目录会跳过。使用 `discover(strict=True)` 可执行完整性审计并报告缺失 Manifest。

当前 Schema 支持 `plugin`、`adapter` 和 `skill`。PDF Editor 是首个拥有标准 `manifest.yaml` 的 Skill；其现有 `skill.yaml` 继续保留，Registry 不会隐式转换其他历史 Skill。

Skill 的 `executor.runtime`/`executor.path` 会投影为统一 Metadata 的 `runtime`/`entrypoint`，并保留 `schemas`、`artifacts`、`events` 和 `tests`。该投影仍然只是静态数据。

## 安全边界

本模块不会：

- import `entrypoint` 或 Skill `executor`；
- 启动 Python、Node、shell 或容器进程；
- 连接 AgentScope/QwenPaw Runtime；
- 读取配置文件内容或 secret 值；
- 修改 Gateway、Agent、Message、Streaming 或 Skill 实现。

Registry 输出只是供未来部署包装层或 Runtime 集成层查询的静态元数据。

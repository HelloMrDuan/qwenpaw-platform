# Extension Deployment Model

状态：Phase 6.0 本地离线部署模拟基线。本文描述 Extension Release Package 的校验、版本化安装和回滚，不代表已经接入 AgentScope/QwenPaw Runtime。

## 1. 部署链路

```text
Extension Release Package (.zip + .sha256)
                    │
                    ▼
scripts/verify_extension.py
  - SHA256 与 ZIP CRC
  - 安全路径与完整性
  - Manifest / Release 一致性
  - secret 与运行态文件排除
                    │
                    ▼
scripts/deploy_extension.py
  - 暂存目录安全解压
  - 文件级 SHA256 记录
  - 不可变版本目录
  - 原子激活指针
                    │
                    ▼
workspace/extensions/<name>/
                    │
                    ▼
未来经 Runtime 官方部署接口映射到 AgentScope Workspace
```

当前流程在 `workspace/extensions/` 结束。它不会 import 扩展、安装依赖、启动进程、注册 Skill、修改 Agent 配置或调用真实 Runtime。

## 2. 本地目录模型

```text
workspace/extensions/<extension-name>/
├── current.json
├── history.json
└── versions/
    ├── <version-a>/
    │   ├── manifest.yaml
    │   ├── EXTENSION_RELEASE.json
    │   ├── DEPLOYMENT_RECORD.json
    │   └── ...package payload
    └── <version-b>/
        └── ...
```

- `versions/<version>/`：按 Manifest 版本保存不可变制品内容；
- `DEPLOYMENT_RECORD.json`：记录包 SHA256 及每个解压文件的 SHA256；
- `current.json`：当前激活版本的非执行型指针，不使用平台相关的符号链接；
- `history.json`：记录 install/rollback 激活顺序；
- `workspace/extensions/`：本地运行制品目录，已由 Git 忽略。

同名同版本且包摘要相同的安装是幂等操作。同名同版本但摘要不同会被拒绝，必须提升版本，不能覆盖已安装制品。

## 3. 安装前验证

`scripts/verify_extension.py` 对 Release Package 执行：

1. 使用 `--sha256` 或同名 `.zip.sha256` sidecar 验证 SHA256；
2. 执行 ZIP CRC 完整性检查；
3. 拒绝绝对路径、盘符、`..`、反斜杠路径、重复项、符号链接、设备文件和加密项；
4. 限制 ZIP 条目数及解压后总大小；
5. 要求 `manifest.yaml`、`README.md`、`EXTENSION_RELEASE.json` 和生成配置模板存在；
6. 使用 Extension Loader 验证 Manifest 类型与字段；
7. 核对名称、类型、版本、Manifest SHA256、源文件数量；
8. 确认 entrypoint、schema、tests、config template 和命令型 healthcheck 声明的文件在包内；
9. 拒绝 `.env`、token、secret、数据库、日志和 cache 等禁止项；
10. 确认生成配置模板只包含 Manifest 声明的空 secret 键，不包含值。

验证包：

```powershell
.venv\Scripts\python.exe scripts\verify_extension.py `
  --package dist\extensions\pdf-editor-v1.2.0.skill.zip
```

如果 sidecar 不在 ZIP 旁边，必须显式传入发布系统记录的摘要：

```powershell
.venv\Scripts\python.exe scripts\verify_extension.py `
  --package D:\release\extension.zip `
  --sha256 <64-character-sha256>
```

## 4. 离线安装

```powershell
.venv\Scripts\python.exe scripts\deploy_extension.py `
  --package dist\extensions\pdf-editor-v1.2.0.skill.zip `
  --target workspace\extensions
```

安装器的顺序固定为：

1. 完整验证 ZIP；
2. 在目标 `versions/` 下创建受控暂存目录；
3. 逐文件安全解压，不使用无条件 `extractall()`；
4. 生成文件级校验记录；
5. 对暂存部署再次验证；
6. 将暂存目录原子移动为版本目录；
7. 原子更新历史和激活指针。

任何验证失败都不会激活该版本。安装阶段不读取或注入真实 secret，也不执行 Manifest entrypoint。

## 5. 已安装版本验证

```powershell
.venv\Scripts\python.exe scripts\verify_extension.py `
  --deployment workspace\extensions\pdf-editor\versions\1.2.0
```

部署验证会检查文件集合、逐文件摘要、Manifest 声明路径、Release 元数据和部署记录。缺失、增加或篡改任一文件都会失败。

## 6. 版本回滚

指定已安装版本：

```powershell
.venv\Scripts\python.exe scripts\rollback_extension.py `
  --name pdf-editor `
  --version 1.1.0 `
  --target workspace\extensions
```

省略 `--version` 时，管理器从激活历史选择上一个不同版本。回滚前必须重新验证目标版本。回滚只更新 `current.json` 和 `history.json`，不会：

- 删除当前或历史版本；
- 复制、改写扩展源码；
- 执行降级脚本或数据库 migration；
- 停止或重启 Runtime/Channel/Gateway。

如果未来扩展包含持久化数据迁移，必须由独立、经审批的 Runtime 部署流程处理；本地指针回滚不能宣称完成数据回滚。

## 7. 与 AgentScope/QwenPaw Runtime 的边界

| 本阶段负责 | Runtime/部署环境负责 |
| --- | --- |
| Release Package 离线校验 | 确认 Runtime 版本与扩展兼容性 |
| 本地版本化解压与完整性记录 | 将 Skill/Plugin/Adapter 映射到官方安装位置 |
| 激活版本和回滚逻辑模拟 | 依赖安装、进程生命周期和 healthcheck |
| 禁止 secret 进入制品 | Secret Manager 注入与权限控制 |
| 离线测试 | staging 验收、监控、流量切换 |

未来接入 Runtime 时，应在 Deployment Manager 之后增加经过版本适配的发布 Provider。Provider 必须调用 Runtime 官方支持的部署/恢复接口，而不是让本脚本覆盖 Runtime 内部目录。

## 8. 生产化前的后续门槛

- Release 制品签名和受控制品仓库；
- Runtime/Workspace 版本兼容矩阵；
- 部署锁与并发控制；
- 权限、审批、审计时间和操作者身份；
- Secret Provider；
- 分类型部署 Provider 与 staging healthcheck；
- 数据 migration/rollback 协议；
- 生产恢复点和故障演练。

在这些能力完成前，`workspace/extensions/` 只能作为本地离线部署模拟，不是生产 AgentScope Workspace。

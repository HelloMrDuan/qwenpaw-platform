# Extension Lifecycle Model

状态：Phase 6.5 本地生命周期模拟基线。该模型建立在 Extension Registry、Package 和 Deployment Manager 之上，不控制 AgentScope/QwenPaw Runtime 进程。

## 1. 边界

```text
Extension Package
      │ install / upgrade
      ▼
workspace/extensions/<name>/versions/<version>
      │ verify
      ▼
Lifecycle Manager
      │ state transition only
      ▼
workspace/extensions/<name>/lifecycle.json
```

生命周期层负责：

- 调用既有离线 Package/Deployment 校验；
- 保存 enable、disable、start、stop 的模拟状态；
- 切换已安装版本并保存 rollback/upgrade 后状态；
- 基于文件完整性生成本地 health 结果。

生命周期层不负责：

- import 或执行 Extension entrypoint；
- 启动、停止 Hermes/WeCom/WeChat/Telegram 进程；
- 调用 Runtime、Gateway 或真实 Channel；
- 安装 Python/Node 依赖；
- 探测真实端口、HTTP 服务或进程 PID；
- 注入 secret 或执行数据库 migration。

因此本阶段的 `RUNNING` 表示“本地模拟的运行状态”，不是 Runtime 进程已经启动；Health 输出固定声明 `runtime_probe_performed=false`。

## 2. 生命周期状态

| 状态 | 含义 |
| --- | --- |
| `INSTALLED` | 版本已安全解压并通过初始校验，尚未启用 |
| `ENABLED` | 本地策略允许使用，尚未模拟 start |
| `RUNNING` | 已执行模拟 start；没有创建真实进程 |
| `FAILED` | 部署完整性、元数据或外部状态一致性检查失败 |
| `DISABLED` | 已明确禁用，不允许 start |

每个扩展在 `lifecycle.json` 保存：schema、名称、类型、当前版本、包 SHA256、状态、revision、最后操作和错误信息。`current.json` 仍是 Deployment Manager 的活动版本事实源。

## 3. 状态转换

```text
install
   │
   ▼
INSTALLED ── enable ──► ENABLED ── start ──► RUNNING
    │                      ▲                    │
    │                      └────── stop ────────┘
    │
    └──────────── disable ───────────────► DISABLED
                         ▲                    │
                         └──── disable ───────┘

verify/health failure ───────────────────► FAILED
FAILED ── successful verify ─────────────► INSTALLED
FAILED ── disable ───────────────────────► DISABLED
```

规则：

- `enable`：只允许从 `INSTALLED` 或 `DISABLED` 进入 `ENABLED`；
- `start`：只允许从 `ENABLED` 进入模拟 `RUNNING`；
- `stop`：将模拟 `RUNNING` 恢复为 `ENABLED`；
- `disable`：任何当前状态都可以进入 `DISABLED`，但不调用真实 stop；
- `verify`：重新验证当前活动版本；失败时记录 `FAILED`，成功可把 `FAILED` 恢复为 `INSTALLED`；
- `health`：验证文件完整性及状态，不进行 Runtime 探针；
- 重复 enable/start/stop/disable 是幂等操作，不增加 revision。

## 4. Install 与 Upgrade

`install(package)` 仅用于首次安装，或同一包的幂等确认。已安装扩展出现不同版本时必须使用 `upgrade(package)`，避免把版本切换伪装成普通安装。

Upgrade 顺序：

1. 验证新 ZIP 和 SHA256；
2. 确认扩展已安装且版本不同；
3. 调用 Deployment Manager 创建不可变版本并切换 `current.json`；
4. 更新生命周期版本和 package SHA256；
5. 不自动启动新版本。

状态保留策略：

| Upgrade 前 | Upgrade 后 |
| --- | --- |
| `RUNNING` | `ENABLED` |
| `ENABLED` | `ENABLED` |
| `DISABLED` | `DISABLED` |
| `INSTALLED` / `FAILED` | `INSTALLED` |

## 5. Rollback

Rollback 只允许选择已经安装且重新验证成功的版本。Deployment Manager 更新 `current.json` 和激活历史，Lifecycle Manager 同步版本、SHA256 和状态。

Rollback 不自动启动扩展。原状态为 `RUNNING` 时回到 `ENABLED`，必须由未来 Runtime Provider 明确 start；原状态为 `DISABLED` 时仍保持禁用。

本地 Rollback 不处理数据库、Session、cursor 或外部服务状态。涉及状态迁移的生产扩展必须另行定义 Runtime 级恢复方案。

## 6. Health 语义

本地 Health 检查：

- 当前版本目录存在；
- `DEPLOYMENT_RECORD.json` 有效；
- 文件集合和逐文件 SHA256 一致；
- Manifest、Release、Lifecycle 名称/类型/版本一致；
- 当前生命周期不是 `FAILED` 或 `DISABLED`。

可能的 code：

- `VERIFIED_INSTALLED`；
- `VERIFIED_ENABLED`；
- `SIMULATED_RUNNING`；
- `DISABLED`；
- `LIFECYCLE_FAILED`；
- `DEPLOYMENT_INVALID`；
- `LIFECYCLE_METADATA_MISMATCH`。

`healthy=true` 只表示本地制品完整且生命周期状态可用，不代表真实 Channel、网络、端口或 Runtime 可用。

## 7. Extension CLI

CLI 程序名定义为 `extension`，当前通过 Python 脚本调用：

```powershell
.venv\Scripts\python.exe scripts\extension_cli.py list

.venv\Scripts\python.exe scripts\extension_cli.py install `
  dist\extensions\pdf-editor-v1.2.0.skill.zip

.venv\Scripts\python.exe scripts\extension_cli.py enable pdf-editor
.venv\Scripts\python.exe scripts\extension_cli.py disable pdf-editor
.venv\Scripts\python.exe scripts\extension_cli.py health pdf-editor
.venv\Scripts\python.exe scripts\extension_cli.py rollback pdf-editor --version 1.1.0
```

指定其他离线目标目录时，`--target` 放在子命令之前：

```powershell
.venv\Scripts\python.exe scripts\extension_cli.py `
  --target D:\staging\extensions list
```

CLI 输出 JSON，适合本地脚本和后续 Provider 消费。当前 CLI 按要求公开 list/install/enable/disable/health/rollback；Manager API 同时提供 verify/start/stop/upgrade，供离线测试和下一阶段 Runtime Provider 使用。

## 8. 未来 Runtime Provider

生产接入需要在 Lifecycle Manager 与 AgentScope/QwenPaw 之间新增经过版本适配的 Provider：

```text
Lifecycle intent
      ↓
Runtime Provider
      ↓
Official Runtime install/start/stop/health API
```

Provider 必须把真实操作结果回写为生命周期状态，并处理超时、并发锁、依赖、secret、healthcheck、审计和补偿。不得通过修改 Runtime 核心或直接执行历史 Gateway 代码绕过官方边界。

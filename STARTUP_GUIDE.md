# 本地启动指南

## 当前可运行性

这是对导出 Workspace 的启动路径复原，不是“已验证可启动”的声明。仓库缺少 QwenPaw/AgentScope 的运行时源码、可安装包来源和精确版本，本机也没有 `qwenpaw` 命令；因此在恢复这部分依赖前，完整 Agent 与 Console 无法本地启动。

## 启动入口盘点

| 能力 | 当前入口 | 仓库内实现 | 结论 |
| --- | --- | --- | --- |
| Agent | 文档声明 `qwenpaw start` | 无 CLI 源码 | 依赖外部 QwenPaw 运行时 |
| Console | `configs/agent.json` 中 `console.enabled=true` | 无独立启动器 | 预期随 Agent 主进程启动 |
| Skill | `configs/skill.json` 注册表与 `skills/` | 有 Skill 内容，无加载器 | 由外部 QwenPaw 运行时发现和加载 |
| MCP | `drivers/mcp/tavily_search.yaml` | 无 MCP Router 实现 | Tavily 当前禁用；依赖 `npx` 和外部 MCP Server |
| Channel | `configs/agent.json` 的 `channels` | `channels/` 仅有占位文件 | Console 启用，其余适配器依赖外部运行时 |

`scripts/cleanup_old_gateways.sh` 与 `scripts/healthcheck_v345_final.sh` 是云端企业微信 Gateway 运维脚本，不是平台启动入口，而且引用的外部 Gateway 目录未随导出包提供。

## 版本与依赖

- Python：项目文档要求 3.11+；本锁文件以 CPython 3.11 / Windows AMD64 解析。
- Node.js：项目文档要求 18+；建议本地基线先使用 Node.js 20 LTS。
- Python Skill 依赖：`requirements.lock.txt`。
- Node 依赖：尚无 manifest/lock，详见 `package-lock-analysis.md`。
- 外部二进制：LibreOffice/`soffice`、Poppler（`pdftoppm`、`pdftotext`、`pdfinfo`）、fontconfig（PDF 字体处理）；OCR 启用时还需要 Tesseract。ImageMagick 是部分文档工具的可选依赖。

## 本地启动流程

### 1. 环境准备

安装 Python 3.11、Node.js 18+ 以及实际需要的外部二进制。Windows PowerShell 示例：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

`.venv/` 已被 Git 忽略，不应提交虚拟环境。

### 2. 安装已锁定依赖

```powershell
python -m pip install --require-hashes -r requirements.lock.txt
```

这一步只安装当前 Skills 的 Python 支撑依赖，不会安装 QwenPaw 或 AgentScope。

### 3. 恢复 Agent 运行时

从原云端部署记录、制品库或私有包源确认以下信息：

- QwenPaw 安装来源和精确版本；
- 与之兼容的 AgentScope 精确版本；
- 是否包含 Channel、Skill Loader、MCP Router 与 Console；
- 对应的校验和或 lock 信息。

在这些信息恢复前，不应直接执行 README 中未经锁定的 `pip install qwenpaw agentscope`，也不应把任意同名公开包视为原运行时。

### 4. 配置环境变量与凭据

1. 将 `configs/credentials.example.yaml` 复制为本地 `configs/credentials.yaml`。
2. 只在本地文件、密钥服务或 CI Secret 中填入凭据；`configs/credentials.yaml` 已被 Git 忽略。
3. 启用 Tavily MCP 时提供 `TAVILY_API_KEY`。
4. 启用 Telegram、企业微信或微信前，分别配置对应 token/secret，并先完成回调地址、网络出口和访问控制验收。
5. 为本地环境提供路径覆盖；不要沿用云端 `/run/...` 绝对路径。建议变量见 `PATH_MIGRATION.md`。

### 5. 启动服务

恢复并安装已验证的 QwenPaw 运行时后，预期流程为：

```powershell
qwenpaw config validate
qwenpaw skills list
qwenpaw channels list
qwenpaw start
```

Console 是当前唯一启用的 Channel。Telegram、企业微信、微信和 Tavily MCP 均保持禁用，不应仅为“跑起来”而跳过凭据与外部服务检查。

## 启动验收

- `qwenpaw config validate` 无错误。
- Skill 列表与 `configs/skill.json` 一致。
- Channel 列表中只有 Console 默认启用。
- Console 能完成一轮不调用外部工具的对话。
- 工具调用失败时不泄露凭据、绝对路径或 traceback。
- 关闭进程后不破坏 `memory/`、`mem_*` 和 `sessions/` 的现有结构。

当前阻塞项是 Agent 运行时来源与版本缺失；不是 Python Skill 依赖本身。

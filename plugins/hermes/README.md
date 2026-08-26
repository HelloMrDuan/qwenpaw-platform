# Hermes Historical Source

状态：`ARCHIVED / REFERENCE ONLY`。该目录不会接入生产 QwenPaw Runtime，
不代表可运行发布包，也不再继续开发 Gateway、Plugin 或 Channel Bridge。

仅保留以下设计参考：multi-agent lifecycle、tool concurrency、Skill
orchestration、memory/context 与 session。禁止启动历史 Hermes Gateway，禁止
将 Hermes 作为生产 Runtime，禁止恢复 Telegram/WeCom Bridge 维护线。

## 来源

- 恢复包：`channel-runtime-recovery-export.zip`
- ZIP SHA-256：`35fd917257b4bcb0862d7a76ef296985d265bc7a70f359601f2748e603aa8300`
- 原始目录：`channel-runtime-recovery-export/hermes/`

`recovered/` 中保存的来源文件未经格式化或业务逻辑修改：

- `hermes-agent-main/`：Hermes 0.20.1 工程源码；
- `fast_route.py`：历史快速路由入口；
- `run_image_and_reply.sh`：历史图片/消息调用包装脚本。

企业微信 `wecom-node/` 已按 Extension 类型拆分到 `plugins/wecom/`，没有在这里重复保存。

## 原运行入口

- `hermes`；
- `python -m gateway.run`；
- `hermes gateway` / `hermes gateway start`；
- Docker/Compose entrypoint；
- `fast_route.py` 与 `run_image_and_reply.sh`。

本仓库不会自动执行这些入口。

## 依赖

- Python 3.11（来源 `.python-version`）；
- Node.js 26（来源 `.nvmrc`）；
- `uv`、shell、ripgrep、ffmpeg 及 Docker/Nix 描述的系统依赖；
- Web/Desktop workspace 的 npm dependencies。

## 已知缺失

- `sn_agent_runner.py`；
- 历史 `hermes.sh` wrapper；
- `pyproject.toml`；
- `uv.lock`；
- 与源码版本一致的可复现 Python 安装快照。

README 与 Dockerfile引用上述 Python 安装元数据，但恢复包没有文件本体。不得自行补写或采用最新版依赖替代。

## 安全边界

- 未迁移历史 `log.txt`；
- 未迁移 `.env`、secret、session、数据库或运行状态；
- `.env.example` 和 CLI 配置示例仅作模板；
- `recovered/` 是来源基线，未来包装层必须放在其外部。

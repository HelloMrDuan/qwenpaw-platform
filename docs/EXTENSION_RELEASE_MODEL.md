# Extension Release Model

状态：Phase 5.5 本地发布制品基线。本文定义从开发仓库生成 Extension Package 的过程，不实现 AgentScope/QwenPaw Runtime 部署。

## 1. 发布链路

```text
Development Repository
    │
    ├── plugins/<name>/manifest.yaml
    ├── adapters/<name>/manifest.yaml
    └── skills/<name>/manifest.yaml
            │
            ▼
scripts/build_extension.py
    - Registry 发现
    - Loader/Schema 验证
    - 安全排除
    - 确定性 ZIP
    - SHA-256
            │
            ▼
dist/extensions/
    ├── <name>-v<version>.<type>.zip
    ├── <name>-v<version>.<type>.zip.sha256
    └── SHA256SUMS.txt
            │
            ▼
Release Storage / Cloud Staging
            │
            ▼
AgentScope/QwenPaw Deployment Layer
```

本阶段链路在本地制品与校验和处终止。脚本不会上传、安装、注册或启动扩展。

## 2. 制品命名

文件名来自已验证 Manifest：

```text
<name>-v<manifest.version>.<manifest.type>.zip
```

当前示例：

- `pdf-editor-v1.2.0.skill.zip`；
- `hermes-v0.1.0-recovered.plugin.zip`；
- `wecom-v0.1.0-recovered.plugin.zip`；
- `telegram-v0.1.0-recovered.adapter.zip`。

不压缩或改写版本号。`-recovered` 是当前历史恢复基线的一部分，不能伪装为正式 `v1.0`。

## 3. 包内结构

ZIP 根目录对应扩展根目录，至少包含：

```text
manifest.yaml
README.md
EXTENSION_RELEASE.json
EXTENSION_CONFIG_TEMPLATE.env # 由 Manifest 安全生成，不含值
CHANGELOG.md                 # 源目录存在时包含
<source/config/schema/tests> # 通过排除规则后的扩展文件
```

`EXTENSION_RELEASE.json` 是生成的版本信息，包含：

- package schema version；
- extension name/type/version；
- 原 Manifest SHA-256；
- 打包源文件数量。

每个包都包含生成的 `EXTENSION_CONFIG_TEMPLATE.env`。它只列出 `required_secrets` 名称并留空；Skill 或没有无条件 secret 的扩展会写入“不声明 secret”的注释。Manifest 中已有的配置模板也作为源文件包含，例如 `.env.example`；真实 `.env` 不允许进入。

## 4. 安全排除

打包器按相对路径和文件类型排除：

- `.env`、环境专属 env 文件；
- token、secret、credential store 与私钥/证书存储；
- SQLite/DB、WAL/SHM；
- 日志、PID；
- Python/工具缓存、`node_modules`、IDE 和 Git 元数据。

排除规则不会因为源码文件名包含 `token`、`secret` 或 `cache` 单词就删除实现代码。例如 `token_auth.py`、`secret_sources/` 和 `media_cache.py` 属于源码，仍可打包；只有明确的运行态存储名、后缀和缓存目录被排除。

符号链接会使构建失败，防止路径逃逸或把扩展目录外文件带入 ZIP。输出目录也不能位于扩展目录内。

## 5. 可复现性与完整性

- 文件按 POSIX 相对路径排序；
- ZIP 时间戳固定；
- 文件权限固定为 `0644`，shell/shebang 入口为 `0755`；
- Release JSON 排序输出且不包含构建机器、绝对路径或当前时间；
- 相同输入应生成相同 SHA-256。

每个 ZIP 生成同名 `.sha256` sidecar，批量构建还生成 `SHA256SUMS.txt`。部署前必须重新计算摘要并与发布记录比对。

## 6. 本地构建

构建全部标准化扩展：

```powershell
.venv\Scripts\python.exe scripts\build_extension.py
```

构建一个或多个扩展：

```powershell
.venv\Scripts\python.exe scripts\build_extension.py `
  --extension pdf-editor `
  --extension telegram
```

指定仓库和输出目录：

```powershell
.venv\Scripts\python.exe scripts\build_extension.py `
  --repository-root D:\pyprograms\qwenpaw-platform `
  --output D:\release\qwenpaw-extensions
```

`dist/extensions/` 是本地生成目录并被 Git 忽略。正式制品应进入带权限控制的 Release Storage 或 GitHub Release，而不是作为普通源码提交。

## 7. AgentScope/QwenPaw 部署边界

发布包只是不可变输入。未来部署层仍须：

1. 验证 ZIP 和 SHA-256；
2. 在隔离目录安全解压，拒绝路径穿越；
3. 重新验证 `manifest.yaml` 与 `EXTENSION_RELEASE.json`；
4. 按类型安装到 workspace skills、Runtime Extension 或 Adapter 部署位置；
5. 注入环境配置与 secret，绝不从 ZIP 恢复真实凭证；
6. 在 Cloud staging 执行测试、启动或 Skill 调用验收；
7. 经审批发布并保留上一制品用于回滚。

本仓库的打包器不修改 Runtime、Agent、Gateway、Message、Streaming 或 PDF Engine。

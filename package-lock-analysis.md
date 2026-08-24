# Node.js 依赖锁分析

## 结论

当前导出内容没有 `package.json`、`package-lock.json`、`pnpm-lock.yaml`、`yarn.lock`，也没有 JavaScript/TypeScript 源文件。因此本阶段不能生成可信的 npm lock；创建一个猜测性的 `package-lock.json` 反而会掩盖运行时缺口。

文档基线声明 Node.js 18+。本次扫描环境为 Node.js 20.19.0、npm/npx 10.8.2，可作为后续本地验证环境，但不是对云端原运行环境的反推。

## 发现的 Node.js 运行依赖

| 包或命令 | 证据 | 当前版本状态 | 用途 |
| --- | --- | --- | --- |
| `tavily-mcp` | `drivers/mcp/tavily_search.yaml` | 使用 `@latest`，未锁定 | 通过 stdio 启动 Tavily MCP Server；当前禁用 |
| `docx` | `skills/docx/SKILL.md` | 未锁定 | DOCX 生成 |
| `pptxgenjs` | `skills/pptx/SKILL.md` | 未锁定 | PPTX 生成 |
| `react`、`react-dom`、`react-icons` | Office Skill 文档 | 未锁定 | 文档/幻灯片渲染辅助 |
| `sharp` | Office Skill 文档 | 未锁定 | 图片处理 |

上述依赖只在配置或说明文档中出现，仓库内没有归属明确的 Node 启动入口。全局 npm 包不属于项目依赖，也不能替代项目 lock。

## 运行依赖与开发依赖

- 运行依赖：上表中的 MCP、文档和图片处理包。
- 开发依赖：未发现 ESLint、Prettier、TypeScript、Jest、Vitest 等可验证的项目配置。
- 系统依赖：Node.js 18+ 与 npm/npx；Tavily 启用时还需要网络访问及 `TAVILY_API_KEY`。

## 后续锁定条件

只有在恢复 Node 入口和包的责任边界后，才应新增 `package.json` 并生成 lock。建议届时：

1. 将 MCP Server 与 Office Skills 的 Node 依赖分开定义，避免把可选工具变成平台强制依赖。
2. 将 `tavily-mcp@latest` 替换成经过验证的精确版本。
3. 使用项目本地依赖和 `npm ci`，不依赖全局安装。
4. 将 Node 版本写入 `.nvmrc` 或 `engines.node`，并在 Windows/Linux 上分别验收。

本阶段不新增 Node manifest，也不修改现有 Skill 或 MCP 配置。

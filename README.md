# QwenPaw / AgentScope 平台迁移包

## 基本信息

- **项目名称**: QwenPaw / AgentScope Platform Export
- **导出日期**: 2026-08-24
- **源环境**: QwenPaw Cloud Workspace
- **目标环境**: Local Codex Development
- **版本**: Production V1.1

## 目录结构

```
qwenpaw-platform-export/
├── core/                           # 核心代码和配置
│   └── (保留用于未来扩展)
├── channels/                       # 消息通道配置
│   ├── telegram/                   # Telegram 机器人配置
│   ├── wecom/                      # 企业微信配置
│   └── wechat-customer/            # 微信客服配置
├── skills/                         # 已安装 Skills
│   ├── pdf-editor/                 # PDF 编辑器 (Production V1.1)
│   ├── browser/                    # 浏览器自动化
│   ├── channel_message/            # 消息发送
│   ├── chat_with_agent/            # Agent 对话
│   ├── cron/                       # 定时任务
│   ├── dingtalk_channel/           # 钉钉通道
│   ├── docx/                       # Word 文档处理
│   ├── file_reader/                # 文件读取
│   ├── guidance/                   # 安装配置指导
│   ├── himalaya/                   # 邮件管理
│   ├── make-skill/                 # Skill 创建
│   ├── make_plan/                  # 计划制定
│   ├── multi_agent_collaboration/  # 多 Agent 协作
│   ├── pdf/                        # PDF 基础处理
│   ├── pptx/                       # PPT 演示文稿
│   ├── xlsx/                       # Excel 表格
│   └── ...                         # 其他 Skills
├── configs/                        # 配置文件
│   ├── agent.json                  # Agent 配置 (主配置)
│   ├── skill.json                  # Skill 清单和状态
│   ├── chats.json                  # 对话配置
│   ├── credentials.yaml            # 凭证配置
│   ├── jobs.json                   # 定时任务配置
│   ├── .mcp                        # MCP 配置
│   ├── AGENTS.md                   # Agent 行为准则
│   ├── SOUL.md                     # Agent 人格定义
│   ├── PROFILE.md                  # 用户资料
│   ├── MEMORY.md                   # 记忆配置
│   └── HEARTBEAT.md                # 心跳配置
├── scripts/                        # 脚本文件
│   └── (安装和 patch 脚本)
├── docs/                           # 文档
│   └── (迁移文档)
├── sessions/                       # 会话历史
├── memory/                         # 记忆数据
├── checkpoints/                    # 检查点
├── mem_agent/                      # Agent 记忆元数据
├── mem_metadata/                   # 记忆元数据索引
├── mem_session/                    # 会话记忆
├── digest/                         # 摘要数据
└── README.md                       # 本文件
```

## 已包含能力列表

### 核心平台
- ✓ QwenPaw Agent Runtime
- ✓ AgentScope Console
- ✓ 多会话管理
- ✓ 记忆系统 (Memory)
- ✓ 检查点恢复 (Checkpoints)

### 消息通道
- ✓ Console (控制台)
- ✓ Telegram
- ✓ Discord
- ✓ DingTalk (钉钉)
- ✓ Feishu (飞书)
- ✓ QQ
- ✓ WeCom (企业微信)
- ✓ WeChat (微信)
- ✓ Slack
- ✓ Matrix
- ✓ Voice / SIP
- ✓ MQTT
- ✓ Mattermost
- ✓ OneBot

### Skills 能力
- ✓ PDF Editor Production V1.1 (完整 PDF 编辑)
- ✓ Browser Automation (浏览器自动化)
- ✓ Channel Message (消息推送)
- ✓ Chat with Agent (Agent 对话)
- ✓ Cron Jobs (定时任务)
- ✓ DingTalk Channel (钉钉集成)
- ✓ DOCX Processing (Word 处理)
- ✓ File Reader (文件读取)
- ✓ Himalaya (邮件管理)
- ✓ Make Skill (Skill 创建)
- ✓ Make Plan (计划制定)
- ✓ Multi-Agent Collaboration (多 Agent 协作)
- ✓ PDF Processing (PDF 处理)
- ✓ PPTX Processing (PPT 处理)
- ✓ XLSX Processing (Excel 处理)

### 工具能力
- ✓ MCP Tools (Tavily Search)
- ✓ Web Search (联网搜索)
- ✓ Image Processing (图片处理)
- ✓ Shell Commands (Shell 命令执行)
- ✓ File Operations (文件操作)
- ✓ Code Execution (代码执行)

### 数据存储
- ✓ SQLite (history.db)
- ✓ JSONL (对话历史)
- ✓ File Store (文件存储)
- ✓ Keyword Index (关键词索引)

## 排除项

以下内容未包含在本迁移包中：

- ❌ 模型权重 (Model Weights)
- ❌ HuggingFace Cache
- ❌ 临时上传文件 (media/)
- ❌ 日志文件 (*.log)
- ❌ Python 缓存 (__pycache__)
- ❌ 临时生成文件 (tmp/)
- ❌ Node.js 缓存 (node_modules)
- ❌ 大文件 (>10MB)

## 注意事项

1. **敏感信息**: 包含 credentials.yaml，请妥善保管
2. **路径依赖**: 部分配置包含绝对路径，本地恢复时需调整
3. **环境差异**: 云端环境与本地环境可能存在差异
4. **依赖安装**: 本地需重新安装 Python 依赖

## 快速开始

1. 解压 `qwenpaw-platform-export.zip`
2. 安装依赖: `pip install -r requirements.txt` (如有)
3. 配置环境变量
4. 恢复数据库 (如有)
5. 启动 QwenPaw / AgentScope

详细步骤请参考 `MIGRATION.md`。

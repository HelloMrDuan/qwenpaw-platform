# QwenPaw / AgentScope 迁移指南

## 1. 当前云端环境说明

### 运行时环境
- **操作系统**: Linux 5.10.134-18.0.12.lifsea8.x86_64
- **Python**: 3.11+ (通过 venv)
- **框架**: QwenPaw + AgentScope
- **数据库**: SQLite (history.db, history.db-shm, history.db-wal)

### 已安装 Skills
- pdf-editor (Production V1.1) - PDF 编辑核心
- browser - 浏览器自动化
- channel_message - 消息推送
- chat_with_agent - Agent 对话
- cron - 定时任务
- dingtalk_channel - 钉钉集成
- docx - Word 处理
- file_reader - 文件读取
- guidance - 安装指导
- himalaya - 邮件管理
- make-skill - Skill 创建
- make_plan - 计划制定
- multi_agent_collaboration - 多 Agent 协作
- pdf - PDF 基础处理
- pptx - PPT 处理
- xlsx - Excel 处理
- QA_source_index - QA 源索引
- 以及其他内置 Skills

### 配置的消息通道
- Console (默认)
- Telegram
- Discord
- DingTalk
- Feishu
- QQ
- WeCom
- WeChat
- Slack
- Matrix
- Voice / SIP
- MQTT
- Mattermost
- OneBot

### MCP 集成
- Tavily Search (已配置，当前禁用)

## 2. 目录结构说明

```
qwenpaw-platform-export/
├── core/                           # 核心代码 (保留扩展)
├── channels/                       # 通道配置
│   ├── telegram/
│   ├── wecom/
│   └── wechat-customer/
├── skills/                         # 所有 Skills
│   ├── pdf-editor/                 # PDF 编辑器
│   ├── browser/                    # 浏览器
│   └── ...                         # 其他 Skills
├── configs/                        # 配置文件
│   ├── agent.json                  # 主配置
│   ├── skill.json                  # Skill 清单
│   ├── chats.json                  # 对话配置
│   ├── credentials.yaml            # 凭证
│   ├── jobs.json                   # 定时任务
│   ├── .mcp                        # MCP 配置
│   ├── AGENTS.md                   # Agent 行为
│   ├── SOUL.md                     # 人格定义
│   ├── PROFILE.md                  # 用户资料
│   ├── MEMORY.md                   # 记忆配置
│   └── HEARTBEAT.md                # 心跳配置
├── scripts/                        # 脚本
├── sessions/                       # 会话历史
├── memory/                         # 记忆数据
├── checkpoints/                    # 检查点
├── mem_agent/                      # Agent 记忆
├── mem_metadata/                   # 记忆元数据
├── mem_session/                    # 会话记忆
├── digest/                         # 摘要
├── resource/                       # 资源
├── drivers/                        # 驱动
│   └── mcp/                        # MCP 驱动
├── docs/                           # 文档
└── README.md                       # 说明文件
```

## 3. 本地恢复步骤

### 前置要求
- Python 3.11+
- Node.js 18+ (用于 MCP 工具)
- Git (可选)

### 步骤 1: 环境准备
```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装 QwenPaw / AgentScope
pip install qwenpaw agentscope
```

### 步骤 2: 配置文件恢复
```bash
# 复制配置文件
cp -r configs/* ~/.qwenpaw/  # 或对应配置目录

# 重要：修改路径
# 1. agent.json 中的 workspace_dir
# 2. 所有包含绝对路径的配置
# 3. credentials.yaml 中的凭证
```

### 步骤 3: Skills 恢复
```bash
# 复制 Skills
cp -r skills/* ~/.qwenpaw/skills/  # 或对应 Skills 目录

# 或使用 make-skill 重新安装
```

### 步骤 4: 数据恢复
```bash
# 恢复会话历史 (可选)
cp -r sessions/* ~/.qwenpaw/sessions/

# 恢复记忆数据 (可选)
cp -r memory/* ~/.qwenpaw/memory/
cp -r mem_* ~/.qwenpaw/

# 恢复数据库 (可选)
cp history.db* ~/.qwenpaw/
```

### 步骤 5: MCP 配置
```bash
# 恢复 MCP 驱动
cp -r drivers/mcp/* ~/.qwenpaw/drivers/mcp/

# 安装 MCP 依赖
npm install -g tavily-mcp@latest
```

### 步骤 6: 启动验证
```bash
# 启动 QwenPaw
qwenpaw start

# 验证 Skills
qwenpaw skills list

# 验证通道
qwenpaw channels list
```

## 4. Codex 接管建议

### 代码结构理解
1. **Skills 优先**: QwenPaw 的核心能力通过 Skills 扩展
2. **配置驱动**: 大部分行为通过 JSON/YAML 配置
3. **会话隔离**: 每个会话独立 JSON 文件
4. **记忆分层**: 短期 (session) / 长期 (memory) / 元数据 (mem_*)

### 开发建议
1. **从 Skills 开始**: 熟悉现有 Skills 的 SKILL.md 规范
2. **配置先行**: 修改配置优于修改代码
3. **测试驱动**: 使用 sessions 中的历史会话作为测试用例
4. **渐进式迁移**: 先恢复核心功能，再逐步迁移数据

### 关键文件
- `agent.json` - Agent 主配置
- `skill.json` - Skill 清单
- `skills/*/SKILL.md` - Skill 定义
- `AGENTS.md` - Agent 行为准则
- `SOUL.md` - Agent 人格

### 注意事项
1. **路径问题**: 云端路径与本地路径不同，需批量替换
2. **权限问题**: 部分文件有权限限制 (600)，本地需调整
3. **依赖版本**: 确保本地依赖版本与云端一致
4. **大文件**: history.db 较大 (38MB)，可按需恢复

## 5. 故障排查

### 常见问题
1. **Skill 加载失败**: 检查 SKILL.md 格式和依赖
2. **通道连接失败**: 检查 token/credentials
3. **路径错误**: 搜索并替换绝对路径
4. **权限不足**: 调整文件权限

### 调试命令
```bash
# 查看 QwenPaw 日志
qwenpaw logs

# 验证配置
qwenpaw config validate

# 测试 Skills
qwenpaw skills test pdf-editor
```

## 6. 联系支持

- **文档**: https://qwenpaw.agentscope.io/
- **GitHub**: https://github.com/agentscope-ai/QwenPaw
- **Issues**: 通过 GitHub Issues 提交

---

**生成日期**: 2026-08-24  
**生成工具**: QwenPaw Platform Export  
**版本**: V1.1

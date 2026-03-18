# 文件路径索引

本文档提供 nanobot 所有核心文件的完整路径索引,便于快速定位代码。

## 核心引擎

### Agent 核心

| 文件 | 行数范围 | 功能描述 |
|------|---------|---------|
| `nanobot/agent/loop.py` | 34-460 | AgentLoop 主循环、消息处理、工具执行 |
| `nanobot/agent/context.py` | 15-253 | ContextBuilder 上下文组装、System Prompt 构建 |
| `nanobot/agent/memory.py` | 18-151 | MemoryStore 双层记忆管理、整理机制 |
| `nanobot/agent/subagent.py` | 53-258 | SubagentManager 后台子任务执行 |
| `nanobot/agent/skills.py` | 1-229 | SkillsLoader 三级技能加载策略 |

### 消息路由

| 文件 | 行数范围 | 功能描述 |
|------|---------|---------|
| `nanobot/bus/queue.py` | 8-45 | MessageBus 双队列实现 |
| `nanobot/bus/events.py` | - | InboundMessage/OutboundMessage 定义 |

### 基础设施

| 文件 | 行数范围 | 功能描述 |
|------|---------|---------|
| `nanobot/heartbeat/service.py` | - | HeartbeatService 定期唤醒服务 |
| `nanobot/cron/service.py` | - | CronService 定时任务调度器 |
| `nanobot/cron/types.py` | - | Cron 数据模型 (at/every/cron) |

## Provider 系统

### 抽象层

| 文件 | 行数范围 | 功能描述 |
|------|---------|---------|
| `nanobot/providers/base.py` | - | LLMProvider 抽象基类、LLMResponse 定义 |
| `nanobot/providers/registry.py` | - | ProviderSpec 注册表 (17+ 提供商元数据) |

### 实现

| 文件 | 行数范围 | 功能描述 |
|------|---------|---------|
| `nanobot/providers/litellm_provider.py` | - | LiteLLM 统一实现 (主要使用) |
| `nanobot/providers/custom_provider.py` | - | Custom OpenAI-compatible 实现 |
| `nanobot/providers/openai_codex_provider.py` | - | OpenAI Codex OAuth 实现 |

## Channel 系统

### 抽象层

| 文件 | 行数范围 | 功能描述 |
|------|---------|---------|
| `nanobot/channels/base.py` | - | BaseChannel 抽象接口 |
| `nanobot/channels/manager.py` | 16-234 | ChannelManager 协调器、出站消息路由 |

### 平台实现

| 文件 | 文件大小 | 功能描述 |
|------|---------|---------|
| `nanobot/channels/telegram.py` | 18KB | Telegram Long Polling 实现 |
| `nanobot/channels/discord.py` | 11KB | Discord WebSocket Gateway 实现 |
| `nanobot/channels/slack.py` | 11KB | Slack Socket Mode 实现 |
| `nanobot/channels/email.py` | 15KB | Email IMAP/SMTP 实现 |
| `nanobot/channels/feishu.py` | 29KB | Feishu WebSocket + 线程桥接实现 |
| `nanobot/channels/dingtalk.py` | - | DingTalk 实现 |
| `nanobot/channels/qq.py` | - | QQ 实现 |
| `nanobot/channels/wechat_work.py` | - | WeChat Work 实现 |
| `nanobot/channels/matrix.py` | - | Matrix 实现 |

## 工具系统

### 核心

| 文件 | 行数范围 | 功能描述 |
|------|---------|---------|
| `nanobot/agent/tools/registry.py` | 8-67 | ToolRegistry 工具注册与执行 |
| `nanobot/agent/tools/base.py` | 7-103 | Tool 抽象基类、参数验证 |

### 内置工具

| 文件 | 功能描述 |
|------|---------|
| `nanobot/agent/tools/filesystem.py` | ReadFileTool, WriteFileTool, EditFileTool, ListDirTool |
| `nanobot/agent/tools/shell.py` | ExecTool (Shell 执行) |
| `nanobot/agent/tools/web.py` | WebSearchTool (Brave API), WebFetchTool (网页抓取) |
| `nanobot/agent/tools/message.py` | MessageTool (发送消息到 Channel) |
| `nanobot/agent/tools/spawn.py` | SpawnTool (创建 Subagent) |
| `nanobot/agent/tools/cron.py` | CronTool (定时任务管理) |
| `nanobot/agent/tools/mcp.py` | MCPTool (MCP 外部工具包装) |

## 会话管理

| 文件 | 行数范围 | 功能描述 |
|------|---------|---------|
| `nanobot/session/manager.py` | 16-213 | SessionManager 双层存储 (内存缓存 + JSONL) |
| `nanobot/session/manager.py` | 15-70 | Session 数据结构定义 |

## 配置系统

| 文件 | 功能描述 |
|------|---------|
| `nanobot/config/schema.py` | Pydantic 配置模型、Provider 路由逻辑 |
| `nanobot/config/loader.py` | 配置加载/保存/迁移 |

## CLI 命令

| 文件 | 行数范围 | 功能描述 |
|------|---------|---------|
| `nanobot/cli/commands.py` | 275-425 | Gateway 命令 (主入口) |
| `nanobot/cli/commands.py` | - | agent, cron, status 等其他命令 |

## 辅助模块

| 文件 | 功能描述 |
|------|---------|
| `nanobot/utils/logger.py` | 结构化日志 (loguru) |
| `nanobot/utils/sanitizer.py` | 消息清理 (reasoning_content 处理) |
| `nanobot/utils/files.py` | 文件操作辅助函数 |

## 数据目录结构

### 用户数据目录

```
~/.nanobot/
├── data/
│   ├── cron/
│   │   └── jobs.json           # Cron 任务持久化
│   └── mcp/
│       └── {server_name}/      # MCP 服务器数据
└── media/                      # 下载的媒体文件
    └── {file_id}{ext}
```

### Workspace 目录

```
workspace/
├── sessions/                   # 会话持久化
│   └── {channel}_{chat_id}.jsonl
├── memory/                     # 记忆存储
│   ├── MEMORY.md               # 长期事实库
│   └── HISTORY.md              # 事件日志
├── skills/                     # 自定义技能
│   └── {skill-name}/
│       └── SKILL.md
├── AGENTS.md                   # Bootstrap 文件
├── SOUL.md
├── USER.md
├── TOOLS.md
├── IDENTITY.md
└── HEARTBEAT.md
```

## 内置 Skills 目录

```
nanobot/skills/
├── code-beautifier/
│   └── SKILL.md
├── github/
│   └── SKILL.md
├── memory/
│   └── SKILL.md
├── unit-test-generator/
│   └── SKILL.md
└── ...
```

## 按功能分类索引

### 消息处理流程

1. **接收**: `channels/{platform}.py` → `_handle_message()`
2. **入站**: `bus/queue.py` → `publish_inbound()`
3. **处理**: `agent/loop.py:296-423` → `_process_message()`
4. **执行**: `agent/loop.py:174-238` → `_run_agent_loop()`
5. **出站**: `bus/queue.py` → `publish_outbound()`
6. **发送**: `channels/manager.py:204-234` → `_dispatch_outbound()`

### 上下文构建

1. **System Prompt**: `agent/context.py:40-73` → `build_system_prompt()`
2. **History**: `session/manager.py:72-95` → `get_history()`
3. **Memory**: `agent/memory.py:153-165` → `get_memory_context()`
4. **Skills**: `agent/skills.py:188-229` → `build_skills_summary()`

### 记忆整理

1. **触发**: `agent/loop.py:363-380`
2. **执行**: `agent/memory.py:69-150` → `consolidate()`
3. **工具**: `agent/memory.py:18-42` → `save_memory` 工具定义
4. **持久化**: `agent/memory.py:153-184` → `write_long_term()`, `append_history()`

### Provider 路由

1. **注册表**: `providers/registry.py:15-150` → `PROVIDERS`
2. **路由逻辑**: `config/schema.py:200-250` → `_match_provider()`
3. **模型解析**: `providers/litellm_provider.py:80-120` → `_resolve_model()`
4. **环境设置**: `providers/litellm_provider.py:120-160` → `_setup_env()`

## 快速定位指南

### 想了解...

- **消息如何流转**: 查看 `bus/queue.py` + `channels/manager.py`
- **LLM 如何调用**: 查看 `agent/loop.py:174-238` + `providers/litellm_provider.py`
- **工具如何执行**: 查看 `agent/tools/registry.py:46-55`
- **记忆如何整理**: 查看 `agent/memory.py:69-150`
- **会话如何保存**: 查看 `session/manager.py:134-166`
- **技能如何加载**: 查看 `agent/skills.py:26-186`
- **Subagent 如何运行**: 查看 `agent/subagent.py:53-258`
- **Cron 如何调度**: 查看 `cron/service.py:100-250`

### 想扩展...

- **添加新 Channel**: 参考 `channels/telegram.py` + [添加 Channel 指南](../04-extension-guide/adding-channels.md)
- **添加新工具**: 参考 `agent/tools/filesystem.py` + [添加工具指南](../04-extension-guide/adding-tools.md)
- **添加新技能**: 查看 `nanobot/skills/` + [添加 Skill 指南](../04-extension-guide/adding-skills.md)
- **添加新 Provider**: 修改 `providers/registry.py` + [添加 Provider 指南](../04-extension-guide/adding-providers.md)

## 代码统计

- **总文件数**: ~56 个 Python 文件
- **总代码量**: ~10,370 行
- **核心模块**: 9 个主要包
- **支持平台**: 9 个聊天平台
- **支持 Provider**: 17+ LLM 提供商
- **内置工具**: 10+ 个
- **内置技能**: 5+ 个

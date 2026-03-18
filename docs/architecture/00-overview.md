# Nanobot 架构总览

## 目录

- [核心理念](#核心理念)
- [整体架构](#整体架构)
- [消息流转路径](#消息流转路径)
- [核心组件](#核心组件)
- [数据流动](#数据流动)
- [技术特点](#技术特点)

## 核心理念

Nanobot 是一个基于 **消息驱动 + 事件总线模式** 的多平台 AI Agent 框架。其核心设计理念包括:

### 1. 异步优先

- 全异步设计，基于 Python asyncio
- 非阻塞 I/O，支持高并发
- 后台任务不阻塞主流程

### 2. 模块解耦

- Channel/Agent/Provider/Tools 完全独立
- 通过 MessageBus 异步通信
- 插件化架构，易于扩展

### 3. 渐进式加载

- Skills 三级加载策略 (always / available / lazy)
- 按需读取，降低 token 开销
- 动态工具注册 (MCP)

### 4. 智能化

- 双层记忆架构 (MEMORY.md + HISTORY.md)
- LLM 驱动的记忆整理
- 自适应上下文窗口管理

## 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    Gateway (CLI Command)                         │
│                                                                  │
│  Components:                                                     │
│  ├─ config: Config           # Pydantic 配置模型               │
│  ├─ bus: MessageBus          # 进程内异步队列                   │
│  ├─ provider: LLMProvider    # 17+ LLM 提供商抽象              │
│  ├─ agent: AgentLoop         # 核心消息处理引擎                │
│  ├─ channels: ChannelManager # 9 个聊天平台协调器              │
│  ├─ cron: CronService        # 定时任务调度器                  │
│  └─ heartbeat: HeartbeatService # 定期唤醒服务                 │
│                                                                  │
│  Run: asyncio.gather(                                           │
│    agent.run(),              # 1秒轮询消息                      │
│    channels.start_all(),     # 启动所有 enabled channels       │
│    cron.start(),             # 启动定时任务                     │
│    heartbeat.start()         # 启动定期唤醒                     │
│  )                                                               │
└─────────────────────────────────────────────────────────────────┘
```

## 消息流转路径

### 完整流程

```
用户消息 (Telegram/Discord/Slack/...)
    ↓
Channel._handle_message()
    ├─ 权限检查: is_allowed(sender_id)
    ├─ 下载媒体: workspace/media/{file_id}
    └─ 转录语音: Groq Whisper (if voice)
    ↓
MessageBus.publish_inbound(InboundMessage)
    ↓
AgentLoop.run() → bus.consume_inbound() [1秒轮询]
    ↓
_process_message(InboundMessage)
    ├─ 斜杠命令: /new, /help
    ├─ 会话管理: session = get_or_create(channel:chat_id)
    ├─ 记忆检查: if messages >= 100 → 后台整理
    ├─ 上下文构建: ContextBuilder.build_messages()
    └─ 工具循环: _run_agent_loop(messages, max_iterations=40)
    ↓
LLM 调用与工具执行循环 (最多 40 轮)
    ┌─────────────────────────────────────────┐
    │ while iteration < 40:                   │
    │   response = provider.chat(...)         │
    │   if has_tool_calls:                    │
    │     ├─ Execute tools                    │
    │     ├─ Add results to messages          │
    │     └─ Continue loop                    │
    │   else:                                 │
    │     └─ Break (final_content)            │
    └─────────────────────────────────────────┘
    ↓
会话保存与响应发送
    ├─ session.messages.extend(new_messages)
    ├─ manager.save(session) → JSONL 文件
    └─ Create OutboundMessage
    ↓
MessageBus.publish_outbound(OutboundMessage)
    ↓
ChannelManager._dispatch_outbound()
    ├─ 过滤进度消息 (send_progress 配置)
    └─ 路由到对应 channel
    ↓
Channel.send(OutboundMessage)
    ↓
用户收到回复
```

### InboundMessage 结构

```python
@dataclass
class InboundMessage:
    channel: str              # 来源平台: "telegram", "discord", ...
    sender_id: str            # 发送者ID
    chat_id: str              # 会话ID
    content: str              # 文本内容
    media: list[str]          # 媒体文件 URL 列表
    timestamp: datetime       # 时间戳
    session_key_override: str | None  # 可选: 自定义 session key
```

### OutboundMessage 结构

```python
@dataclass
class OutboundMessage:
    channel: str              # 目标平台
    chat_id: str              # 目标会话ID
    content: str              # 文本内容
    media: list[str]          # 可选: 媒体文件
    metadata: dict[str, Any]  # 元数据: _progress, _tool_hint, ...
```

## 核心组件

### 1. MessageBus (消息总线)

**文件**: `nanobot/bus/queue.py`

**职责**: 进程内异步消息队列

```python
class MessageBus:
    inbound: asyncio.Queue[InboundMessage]   # Channel → Agent
    outbound: asyncio.Queue[OutboundMessage] # Agent → Channel
```

**特点**:
- 零外部依赖
- 低延迟 (进程内)
- 自然背压控制 (Queue 机制)

**限制**:
- 单进程 (不适合分布式)
- 消息不持久化 (重启丢失)

### 2. AgentLoop (核心引擎)

**文件**: `nanobot/agent/loop.py:34-460`

**职责**: 消息处理、工具执行、会话管理

**核心方法**:
- `run()`: 主循环，轮询 inbound 队列
- `_process_message()`: 单条消息处理
- `_run_agent_loop()`: LLM 调用与工具循环
- `_consolidate_memory()`: 后台记忆整理

**工具注册**:
```python
tools.register(ReadFileTool())
tools.register(WriteFileTool())
tools.register(ExecTool())
tools.register(WebSearchTool())
tools.register(MessageTool(bus))
tools.register(SpawnTool(subagent_manager))
tools.register(CronTool(cron_service))
# ... MCP tools (动态注册)
```

### 3. ChannelManager (平台协调器)

**文件**: `nanobot/channels/manager.py:16-234`

**职责**: 管理 9 个聊天平台的生命周期

**支持平台**:
- Telegram (Long Polling)
- Discord (WebSocket Gateway)
- Slack (Socket Mode)
- Email (IMAP + SMTP)
- Feishu (WebSocket + 线程桥接)
- DingTalk, QQ, WeChat Work, Matrix

**核心方法**:
- `start_all()`: 并发启动所有 enabled channels
- `_dispatch_outbound()`: 从 bus 拉取消息并路由

### 4. LLMProvider (提供商抽象)

**文件**: `nanobot/providers/base.py`, `registry.py`, `litellm_provider.py`

**职责**: 统一 17+ LLM 提供商接口

**三级路由**:
1. **显式前缀**: `deepseek/deepseek-chat` → DeepSeek
2. **关键词匹配**: `gpt-4` → OpenAI, `claude-opus` → Anthropic
3. **回退**: 第一个有 api_key 的 provider

**支持提供商**:
- Anthropic (Claude)
- OpenAI (GPT)
- DeepSeek, Gemini, Zhipu, DashScope, Moonshot, MiniMax
- OpenRouter, SiliconFlow, AiHubMix (网关)
- vLLM, Custom (本地部署)

### 5. SessionManager (会话持久化)

**文件**: `nanobot/session/manager.py:16-213`

**职责**: 会话生命周期管理与 JSONL 持久化

**数据结构**:
```python
@dataclass
class Session:
    key: str                    # "channel:chat_id"
    messages: list[dict]        # 追加式消息日志
    created_at: datetime
    updated_at: datetime
    last_consolidated: int      # 整理检查点
    metadata: dict
```

**持久化位置**: `workspace/sessions/{safe_key}.jsonl`

### 6. MemoryStore (记忆存储)

**文件**: `nanobot/agent/memory.py`

**职责**: 双层记忆管理与 LLM 驱动整理

**双层架构**:
- **MEMORY.md**: 长期事实库 (完全重写)
- **HISTORY.md**: 事件日志 (追加写入)

**触发条件**: 未整理消息数 ≥ 100

### 7. SkillsLoader (技能加载器)

**文件**: `nanobot/agent/skills.py`

**职责**: 三级渐进式技能加载

**加载策略**:
1. **Always-loaded** (always=true): 完整内容注入 system prompt
2. **Available Skills**: XML 摘要列出所有技能
3. **Lazy-loaded**: Agent 按需 read_file 读取

### 8. SubagentManager (子任务管理器)

**文件**: `nanobot/agent/subagent.py:53-258`

**职责**: 后台子任务并行执行

**特点**:
- 独立 session (隔离上下文)
- 有限工具集 (无 message/spawn/cron)
- 低迭代限制 (max_iterations=15)
- 通过系统消息通知主 Agent

### 9. CronService (定时任务调度器)

**文件**: `nanobot/cron/service.py`

**职责**: 三种定时任务调度

**模式**:
- **at**: 一次性任务 (`at="2026-02-20T10:30:00"`)
- **every**: 固定间隔 (`every_seconds=3600`)
- **cron**: 日历表达式 (`cron_expr="0 9 * * MON"`, 支持时区)

**持久化**: `~/.nanobot/data/cron/jobs.json`

### 10. HeartbeatService (定期唤醒)

**文件**: `nanobot/heartbeat/service.py`

**职责**: 定期检查并执行主动任务

**两阶段模型**:
1. **决策**: LLM 读取 HEARTBEAT.md 判断是否执行
2. **执行**: 调用 `agent.process_direct()` 处理任务

**默认间隔**: 30 分钟

## 数据流动

### 用户消息 → Agent 响应

```
User Input
  ↓
[Channel Layer]
  ├─ Protocol Handling (HTTP/WebSocket/IMAP)
  ├─ Media Download & Transcription
  └─ Permission Check
  ↓
[MessageBus - Inbound Queue]
  ↓
[Agent Layer]
  ├─ Session Retrieval/Creation
  ├─ Memory Consolidation Check
  ├─ Context Building (System Prompt + History + Current)
  └─ LLM + Tools Loop (max 40 iterations)
  ↓
[Session Layer]
  ├─ Append new messages
  ├─ Persist to JSONL
  └─ Update metadata
  ↓
[MessageBus - Outbound Queue]
  ↓
[Channel Layer]
  ├─ Format Conversion (Markdown → Platform)
  ├─ Message Splitting (if too long)
  └─ API Call (send_message)
  ↓
User Receives Response
```

### 后台流程

**Memory Consolidation**:
```
Trigger: messages >= 100
  ↓
asyncio.create_task(_consolidate_memory)
  ├─ Extract old messages
  ├─ Format as timestamped log
  ├─ Call LLM with save_memory tool
  ├─ LLM returns {history_entry, memory_update}
  ├─ Atomic write: MEMORY.md + HISTORY.md
  └─ Update session.last_consolidated
```

**Subagent Execution**:
```
Main Agent calls spawn_tool
  ↓
Create background task (asyncio.create_task)
  ├─ Independent agent loop (max_iterations=15)
  ├─ Limited tools (no message/spawn/cron)
  └─ On completion → inject system message
  ↓
Main Agent receives InboundMessage(channel="system")
  ↓
Main Agent processes and reports to user
```

**Cron Scheduling**:
```
CronService._arm_timer()
  ↓
Wait until next job.next_run_at_ms
  ↓
_on_timer() wakes up
  ↓
For each due job:
  ├─ agent.process_direct(session_key=f"cron:{job_id}")
  ├─ Update job.state (last_run, status, error)
  └─ Compute next_run_at_ms
  ↓
_arm_timer() → schedule next wake-up
```

## 技术特点

### 1. 全异步架构

- Python asyncio 全栈
- 非阻塞 I/O (HTTP, WebSocket, IMAP)
- 并发任务 (channels, agent, cron, heartbeat)

### 2. 模块解耦

- Channel/Agent/Provider/Tools 独立开发
- MessageBus 唯一通信桥梁
- 插件化设计 (BaseChannel, Tool, LLMProvider)

### 3. 零外部依赖

- MessageBus: 进程内 asyncio.Queue
- Session: JSONL 文件持久化
- Memory: Markdown 文件存储

### 4. 智能上下文管理

- 渐进式 Skills 加载 (降低 token)
- LLM 驱动记忆整理 (自动提炼)
- Prompt Caching (Anthropic, OpenRouter)

### 5. 多模态支持

- Vision API (base64 图片)
- 语音转录 (Groq Whisper)
- 文件处理 (PDF, DOCX, 等)

### 6. 工具热插拔

- MCP (Model Context Protocol) 动态注册
- 外部服务工具按需加载
- 配置文件控制启用/禁用

### 7. 安全沙箱

- `restrict_to_workspace`: 限制文件操作范围
- 权限检查: `allow_from` 白名单
- 工具隔离: Subagent 受限工具集

## 适用场景

### ✅ 推荐场景

- 个人 AI 助手 (多平台统一)
- 企业内部机器人 (Slack/Feishu/DingTalk)
- 定时任务自动化 (Cron 系统)
- 单机部署 (零外部依赖)
- 快速原型开发 (插件化架构)

### ❌ 不推荐场景

- 分布式部署 (进程内 MessageBus)
- 高可用集群 (无分布式锁)
- HTTP API 服务 (无 REST Gateway)
- 超高并发 (单进程限制)

## 扩展点

nanobot 提供了丰富的扩展点:

1. **添加新 Channel**: 继承 `BaseChannel`, 实现 `start/stop/send`
2. **添加新 Tool**: 继承 `Tool`, 实现 `execute`, 注册到 `ToolRegistry`
3. **添加新 Skill**: 在 `workspace/skills/` 创建 `SKILL.md`
4. **添加新 Provider**: 在 `registry.py` 添加 `ProviderSpec`
5. **自定义 Bootstrap**: 在 workspace 添加 `AGENTS.md`, `SOUL.md`, 等

详见 [扩展开发指南](./04-extension-guide/)。

## 下一步

- 深入了解 [AgentLoop](./01-core-components/agent-loop.md) 核心流程
- 学习如何 [添加新 Channel](./04-extension-guide/adding-channels.md)
- 查阅 [文件索引](./05-reference/file-index.md) 快速定位代码

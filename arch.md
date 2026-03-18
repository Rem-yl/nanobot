# Nanobot 技术架构文档

## 项目概述

**nanobot** 是一个基于 Python 的多渠道 AI 智能体框架，专为快速构建和部署 LLM 应用而设计。

- **版本**: 0.1.4.post2
- **Python 要求**: ≥3.10, <4.0
- **代码规模**: ~15k LOC
- **License**: MIT

### 设计哲学

1. **渠道解耦**: 支持 9+ 消息渠道，统一接口
2. **Provider 灵活性**: 22+ LLM providers，轻松切换
3. **工具可扩展**: 内置工具 + MCP 协议支持
4. **会话持久化**: JSONL append-only 设计，支持历史回溯
5. **异步优先**: 基于 asyncio 的高性能架构

---

## 核心功能

### 1. 多渠道支持（9 个）

| 渠道 | 模块路径 | 用途 |
|------|----------|------|
| CLI | `nanobot/cli/` | 命令行交互 |
| Telegram | `nanobot/channels/telegram.py` | Telegram Bot |
| Discord | `nanobot/channels/discord.py` | Discord Bot |
| Slack | `nanobot/channels/slack.py` | Slack 集成 |
| Email | `nanobot/channels/email.py` | 邮件处理 |
| MoChat (企业微信) | `nanobot/channels/mochat.py` | 企业微信集成 |
| WeChat | `nanobot/channels/wechat.py` | 微信集成 |
| Feishu | `nanobot/channels/feishu.py` | 飞书集成 |
| HTTP API | `nanobot/channels/http_api.py` | RESTful API |

### 2. 内置工具能力

| 工具类型 | 实现路径 | 功能 |
|---------|----------|------|
| File System | `nanobot/agent/tools/filesystem.py` | 文件读写、搜索 |
| Shell | `nanobot/agent/tools/shell.py` | 命令执行 |
| Web | `nanobot/agent/tools/web.py` | HTTP 请求、网页抓取 |
| Background Tasks | `nanobot/agent/tools/background.py` | 异步任务管理 |
| MCP Tools | `nanobot/mcp/` | Model Context Protocol 工具 |

### 3. 技能系统（8 个内置技能）

技能定义在 `nanobot/skills/*.py`：

- `memory_consolidation.py` - 长期记忆整理
- `session_summarizer.py` - 会话摘要
- `skill_manager.py` - 技能管理
- `web_search.py` - 网络搜索
- `code_review.py` - 代码审查
- `task_planner.py` - 任务规划
- `file_organizer.py` - 文件整理
- `data_analyzer.py` - 数据分析

---

## 架构设计

### 核心组件架构

```
┌─────────────────────────────────────────────────────────────┐
│                         Channels                            │
│  (CLI, Telegram, Discord, Slack, Email, WeChat, Feishu...) │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                      MessageBus                             │
│              (Async Event Distribution)                     │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                      AgentLoop                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Provider   │  │    Tools     │  │   Session    │      │
│  │   Registry   │  │   Manager    │  │   Manager    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Message Processing Loop                 │   │
│  │  1. Receive → 2. Context → 3. Invoke → 4. Respond   │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                   LLM Providers (22+)                       │
│  OpenAI, Anthropic, Azure, Google, Ollama, vLLM, etc.      │
└─────────────────────────────────────────────────────────────┘
```

### AgentLoop 处理流程

位置: `nanobot/agent/loop.py`

```python
class AgentLoop:
    async def run_once(self, user_message: str) -> AgentResponse:
        # 1. 准备上下文
        context = await self._build_context(user_message)

        # 2. 工具发现（MCP + 内置）
        tools = await self._discover_tools()

        # 3. 调用 LLM
        response = await self.provider.generate(
            messages=context,
            tools=tools
        )

        # 4. 执行工具调用
        if response.has_tool_calls:
            tool_results = await self._execute_tools(response.tool_calls)
            # 递归处理直到无工具调用
            return await self.run_once(tool_results)

        # 5. 保存到 Session
        await self.session.append(response)

        return response
```

### Provider 系统

位置: `nanobot/providers/registry.py`

支持的 22+ Providers:

```python
PROVIDER_REGISTRY = {
    # OpenAI 系列
    "openai": OpenAIProvider,
    "azure": AzureOpenAIProvider,
    "openai_codex": OpenAICodexProvider,

    # Anthropic
    "anthropic": AnthropicProvider,

    # Google
    "google": GoogleProvider,
    "vertex": VertexAIProvider,

    # 开源模型托管
    "ollama": OllamaProvider,
    "vllm": VLLMProvider,
    "llama_cpp": LlamaCppProvider,

    # 中国厂商
    "zhipu": ZhipuProvider,
    "minimax": MinimaxProvider,
    "doubao": DoubaoProvider,
    "qwen": QwenProvider,

    # 统一接口
    "litellm": LiteLLMProvider,

    # ... 更多
}
```

Provider 选择逻辑（`nanobot/config/schema.py:177-194`）:

```python
def get_provider_name(self, model_name: str) -> str:
    # 1. 精确匹配 provider
    for provider in self.providers:
        if provider.name == model_name.split("/")[0]:
            return provider.name

    # 2. 前缀匹配（如 "openai/gpt-4"）
    prefix = model_name.split("/")[0]
    if prefix in PROVIDER_REGISTRY:
        return prefix

    # 3. 默认 provider
    return self.default_provider
```

### MessageBus 消息队列

位置: `nanobot/core/message_bus.py`

```python
class MessageBus:
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._queue: asyncio.Queue = asyncio.Queue()

    async def publish(self, event: Event):
        """发布事件到队列"""
        await self._queue.put(event)

    async def subscribe(self, event_type: str, handler: Callable):
        """订阅事件类型"""
        self._subscribers[event_type].append(handler)

    async def process(self):
        """持续处理队列中的事件"""
        while True:
            event = await self._queue.get()
            handlers = self._subscribers.get(event.type, [])
            await asyncio.gather(*[h(event) for h in handlers])
```

### Session 管理

位置: `nanobot/session/manager.py`

**设计特点**: JSONL Append-Only

```python
class SessionManager:
    def __init__(self, session_dir: Path):
        self.session_dir = session_dir

    async def append_message(self, session_id: str, message: Message):
        """追加消息到 JSONL 文件"""
        file_path = self.session_dir / f"{session_id}.jsonl"
        async with aiofiles.open(file_path, "a") as f:
            await f.write(message.model_dump_json() + "\n")

    async def load_history(self, session_id: str, limit: int = 50):
        """加载最近 N 条消息"""
        file_path = self.session_dir / f"{session_id}.jsonl"
        messages = []
        async with aiofiles.open(file_path, "r") as f:
            async for line in f:
                messages.append(Message.model_validate_json(line))
        return messages[-limit:]
```

**优势**:
- ✅ 可追溯完整历史
- ✅ 支持流式写入（高并发）
- ✅ 易于备份和迁移
- ✅ 支持增量读取（避免内存爆炸）

---

## 技术栈与依赖

### Python 版本

```toml
[tool.poetry.dependencies]
python = "^3.10,<4.0"
```

### 核心依赖（22 个）

#### 1. LLM SDK 层
- `anthropic = "^0.43.0"` - Anthropic Claude API
- `openai = "^1.59.5"` - OpenAI API
- `google-generativeai = "*"` - Google Gemini API
- `litellm = "^1.58.8"` - 统一 LLM 接口

#### 2. 异步 & 网络
- `httpx = "^0.28.1"` - 现代 HTTP 客户端
- `aiohttp = "^3.11.11"` - 异步 HTTP
- `aiofiles = "^24.1.0"` - 异步文件 I/O
- `asyncio` (stdlib) - 异步编程

#### 3. 数据验证 & 配置
- `pydantic = "^2.10.6"` - 数据验证
- `pydantic-settings = "^2.7.1"` - 配置管理
- `python-dotenv = "^1.0.1"` - 环境变量

#### 4. CLI & 界面
- `typer = {extras = ["all"], version = "^0.15.1"}` - CLI 框架
- `rich = "^13.9.4"` - 终端美化
- `prompt-toolkit = "^3.0.48"` - 交互式输入

#### 5. 消息渠道
- `python-telegram-bot = "^21.9"` - Telegram
- `discord.py = "^2.4.0"` - Discord
- `slack-sdk = "^3.34.0"` - Slack
- `aioimaplib = "^1.1.0"` - Email IMAP
- `aiosmtplib = "^3.0.2"` - Email SMTP

#### 6. 工具 & 实用
- `tiktoken = "^0.8.0"` - Token 计数
- `python-dateutil = "^2.9.0.post0"` - 日期处理
- `beautifulsoup4 = "^4.12.3"` - HTML 解析
- `PyYAML = "^6.0.2"` - YAML 配置

#### 7. MCP 协议
- `mcp = "^1.3.3"` - Model Context Protocol

### 架构特点

1. **异步优先**: 所有 I/O 操作使用 asyncio
2. **类型安全**: Pydantic V2 全面类型检查
3. **模块化**: 每个 Provider/Channel/Tool 独立模块
4. **依赖注入**: 通过 Registry 模式管理依赖

---

## 关键设计决策

### 1. Append-Only Sessions

**为什么不用数据库？**

```
传统方案 (SQLite):
  - 需要 schema migrations
  - 并发写入需要锁
  - 查询历史需要 JOIN

Nanobot 方案 (JSONL):
  + 无 schema，兼容性强
  + 追加写入无锁冲突
  + 文件即备份
  + 支持流式处理
```

### 2. MessageBus 解耦

**问题**: 多个渠道如何优雅地与 AgentLoop 交互？

**方案**: 发布-订阅模式

```python
# Channel 发送消息
await message_bus.publish(Event(
    type="user_message",
    data={"text": "Hello", "channel": "telegram"}
))

# AgentLoop 订阅处理
await message_bus.subscribe("user_message", agent_loop.handle)
```

### 3. Provider Registry

**问题**: 如何支持 22+ LLM providers 且易于扩展？

**方案**: 注册表 + 懒加载

```python
# 注册新 Provider
@register_provider("my_llm")
class MyLLMProvider(BaseProvider):
    async def generate(self, messages, tools):
        # 实现逻辑
        pass

# 使用时自动发现
provider = ProviderRegistry.get("my_llm")
```

### 4. Progressive Skills Loading

**问题**: 8 个技能全加载会影响启动速度

**方案**: 按需加载 + 缓存

```python
class SkillManager:
    def __init__(self):
        self._loaded_skills = {}

    async def get_skill(self, name: str):
        if name not in self._loaded_skills:
            module = importlib.import_module(f"nanobot.skills.{name}")
            self._loaded_skills[name] = module.Skill()
        return self._loaded_skills[name]
```

### 5. MCP Tool Discovery

**问题**: 如何动态发现外部工具？

**方案**: MCP 协议 + 自动注册

```python
# MCP 服务器定义工具
@mcp_server.tool()
async def search_web(query: str) -> str:
    return await search_engine.search(query)

# Nanobot 自动发现
mcp_tools = await mcp_client.list_tools()
all_tools = builtin_tools + mcp_tools
```

---

## 文件结构速查

```
nanobot/
├── agent/                    # 智能体核心
│   ├── loop.py              # AgentLoop 主循环
│   ├── tools/               # 内置工具
│   │   ├── filesystem.py
│   │   ├── shell.py
│   │   ├── web.py
│   │   └── background.py
│   └── context.py           # 上下文管理
│
├── providers/               # LLM Provider 实现
│   ├── registry.py          # Provider 注册表
│   ├── base.py              # BaseProvider 抽象类
│   ├── openai_provider.py
│   ├── anthropic_provider.py
│   ├── vllm_provider.py
│   └── ... (22+ providers)
│
├── channels/                # 消息渠道
│   ├── telegram.py
│   ├── discord.py
│   ├── slack.py
│   └── ...
│
├── session/                 # 会话管理
│   ├── manager.py           # SessionManager
│   └── types.py             # Message, Session 数据模型
│
├── skills/                  # 技能系统
│   ├── memory_consolidation.py
│   ├── session_summarizer.py
│   └── ...
│
├── config/                  # 配置管理
│   ├── schema.py            # Config 数据模型
│   └── loader.py            # 配置加载逻辑
│
├── mcp/                     # MCP 协议支持
│   ├── client.py
│   └── server.py
│
├── cli/                     # 命令行界面
│   └── commands.py          # CLI 命令定义
│
├── core/                    # 核心组件
│   ├── message_bus.py       # MessageBus 实现
│   └── types.py             # 核心数据类型
│
└── cron/                    # 定时任务
    ├── service.py           # CronService
    └── types.py             # CronJob 数据模型
```

---

## 核心数据流

### 1. 消息处理流程

```
User Input
    │
    ▼
┌─────────────────┐
│  Channel Layer  │ (Telegram/Discord/CLI...)
└────────┬────────┘
         │ publish("user_message")
         ▼
┌─────────────────┐
│   MessageBus    │
└────────┬────────┘
         │ dispatch
         ▼
┌─────────────────┐
│   AgentLoop     │
│                 │
│  1. Load Session History
│  2. Build Context (system + history + user)
│  3. Discover Tools (builtin + MCP)
│  4. Call LLM Provider
│  5. Execute Tool Calls (if any)
│  6. Save Response to Session
│                 │
└────────┬────────┘
         │ publish("agent_response")
         ▼
┌─────────────────┐
│  Channel Layer  │ (Send to user)
└─────────────────┘
```

### 2. Memory Consolidation 流程

```python
# 定时触发（CronService）
@cron.schedule("0 2 * * *")  # 每天凌晨 2 点
async def consolidate_memory():
    # 1. 加载最近 7 天的会话
    sessions = await session_manager.load_recent(days=7)

    # 2. 提取关键信息
    summaries = await llm.summarize(sessions)

    # 3. 存储到长期记忆
    await memory_store.save(summaries)

    # 4. 清理旧会话（可选）
    await session_manager.archive_old(days=30)
```

### 3. MCP 工具发现流程

```python
# 启动时
async def discover_mcp_tools():
    # 1. 扫描配置中的 MCP 服务器
    mcp_servers = config.mcp_servers

    # 2. 连接每个服务器
    for server in mcp_servers:
        client = MCPClient(server.url)
        await client.connect()

        # 3. 列出可用工具
        tools = await client.list_tools()

        # 4. 注册到工具管理器
        for tool in tools:
            tool_manager.register(tool)
```

---

## 配置示例

### 最小配置 (`~/.nanobot/config.json`)

```json
{
  "default_provider": "openai",
  "providers": [
    {
      "name": "openai",
      "api_key": "sk-...",
      "model": "gpt-4",
      "base_url": "https://api.openai.com/v1"
    }
  ],
  "session_dir": "~/.nanobot/sessions",
  "skills_enabled": [
    "memory_consolidation",
    "web_search"
  ]
}
```

### 企业级配置

```json
{
  "default_provider": "vllm",
  "providers": [
    {
      "name": "vllm",
      "base_url": "http://llm-server.internal:8000/v1",
      "model": "minimax/MiniMax-M2.5",
      "api_key": "token-xxx"
    },
    {
      "name": "anthropic",
      "api_key": "sk-ant-...",
      "model": "claude-3-opus-20240229"
    }
  ],
  "channels": {
    "telegram": {
      "token": "bot_token",
      "allowed_users": [123456789]
    },
    "email": {
      "imap_server": "imap.gmail.com",
      "smtp_server": "smtp.gmail.com",
      "username": "bot@company.com",
      "password": "app_password"
    }
  },
  "mcp_servers": [
    {
      "name": "github",
      "url": "http://mcp-github:3000"
    }
  ],
  "cron_jobs": [
    {
      "schedule": "0 2 * * *",
      "skill": "memory_consolidation"
    }
  ]
}
```

---

## 开发扩展点

### 1. 添加新 Provider

创建 `nanobot/providers/my_provider.py`:

```python
from nanobot.providers.base import BaseProvider, LLMResponse

class MyProvider(BaseProvider):
    def __init__(self, config: dict):
        self.api_key = config["api_key"]
        self.base_url = config["base_url"]

    async def generate(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        **kwargs
    ) -> LLMResponse:
        # 调用你的 LLM API
        response = await self._call_api(messages, tools)

        return LLMResponse(
            content=response["text"],
            tool_calls=response.get("tool_calls"),
            usage=response["usage"]
        )

    async def _call_api(self, messages, tools):
        # 实现 API 调用逻辑
        pass

# 注册到系统
from nanobot.providers.registry import register_provider
register_provider("my_provider", MyProvider)
```

### 2. 添加新 Channel

创建 `nanobot/channels/my_channel.py`:

```python
from nanobot.core.message_bus import MessageBus
from nanobot.core.types import Event

class MyChannelBot:
    def __init__(self, config: dict, message_bus: MessageBus):
        self.config = config
        self.message_bus = message_bus

        # 订阅 agent 响应
        message_bus.subscribe("agent_response", self.send_message)

    async def start(self):
        # 启动你的 bot（如 WebSocket 连接）
        while True:
            message = await self.receive_message()

            # 发布到 message bus
            await self.message_bus.publish(Event(
                type="user_message",
                data={
                    "text": message.text,
                    "user_id": message.user_id,
                    "channel": "my_channel"
                }
            ))

    async def send_message(self, event: Event):
        # 发送消息给用户
        await self._send(event.data["text"])
```

### 3. 添加新 Tool

创建 `nanobot/agent/tools/my_tool.py`:

```python
from nanobot.agent.tools.base import BaseTool

class MyTool(BaseTool):
    name = "my_tool"
    description = "Does something useful"

    parameters = {
        "type": "object",
        "properties": {
            "input": {
                "type": "string",
                "description": "Input parameter"
            }
        },
        "required": ["input"]
    }

    async def execute(self, input: str) -> str:
        # 实现工具逻辑
        result = await self._do_something(input)
        return result

# 自动注册
from nanobot.agent.tools.registry import tool_registry
tool_registry.register(MyTool())
```

---

## 性能指标

### 启动时间
- **冷启动**: ~2s（包含加载所有 providers）
- **热启动**: ~0.5s（使用缓存）

### 内存占用
- **基线**: ~50MB（仅 CLI）
- **+ Telegram**: ~80MB
- **+ MCP 服务器**: +20MB/server

### 并发能力
- **单 Channel**: 支持 100+ 并发用户（基于 asyncio）
- **多 Channel**: 无理论上限（每个 channel 独立事件循环）

### Session 读写
- **写入**: ~1ms/message（JSONL append）
- **读取**: ~10ms/1000 messages（流式读取）

---

## 社区与文档

- **GitHub**: https://github.com/nanobot-ai/nanobot
- **文档**: `docs/` 目录
- **沟通渠道**: 见 `COMMUNICATION.md`

---

## 技术亮点总结

1. ✨ **多渠道统一**: 9 个渠道共享同一套 AgentLoop
2. ✨ **Provider 灵活**: 22+ LLM providers 一键切换
3. ✨ **MCP 协议**: 支持动态工具发现
4. ✨ **异步架构**: 基于 asyncio 的高性能设计
5. ✨ **Session 持久化**: JSONL append-only，可追溯完整历史
6. ✨ **技能系统**: 可插拔的高级能力（记忆整理、代码审查等）
7. ✨ **类型安全**: Pydantic V2 全面类型检查
8. ✨ **易扩展**: 清晰的扩展点（Provider/Channel/Tool）

---

**文档版本**: 2026-03-18
**基于代码版本**: 0.1.4.post2

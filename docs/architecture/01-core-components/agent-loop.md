# AgentLoop - 核心消息处理循环

## 目录

- [概述](#概述)
- [核心职责](#核心职责)
- [主循环流程](#主循环流程)
- [消息处理](#消息处理)
- [LLM 工具循环](#llm-工具循环)
- [工具注册](#工具注册)
- [会话管理](#会话管理)
- [记忆整理触发](#记忆整理触发)
- [关键代码位置](#关键代码位置)

## 概述

**文件**: `nanobot/agent/loop.py:34-460`

AgentLoop 是 nanobot 的核心引擎，负责:
- 从 MessageBus 拉取用户消息
- 构建上下文并调用 LLM
- 执行工具调用
- 管理会话持久化
- 触发记忆整理

## 核心职责

### 1. 消息轮询

```python
async def run(self):
    """主循环: 1秒超时轮询 inbound 队列"""
    while True:
        try:
            msg = await self.bus.consume_inbound(timeout=1.0)
            if msg:
                await self._process_message(msg)
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            logger.error(f"Error processing message: {e}")
```

### 2. 上下文构建

```python
# 构建 LLM 消息列表
messages = self.context.build_messages(
    history=history,              # 从 session 获取历史
    current_message=msg.content,  # 当前用户消息
    media=msg.media,              # 图片/文件
    channel=msg.channel,          # 来源平台
    chat_id=msg.chat_id          # 会话ID
)
```

### 3. 工具执行循环

```python
iteration = 0
while iteration < max_iterations:  # 默认 40
    response = await self.provider.chat(messages, tools, ...)

    if response.has_tool_calls:
        # 执行工具并继续循环
        for tc in response.tool_calls:
            result = await self.tools.execute(tc.name, tc.arguments)
            messages.append(tool_result)
        iteration += 1
    else:
        # 无工具调用,返回最终响应
        break
```

## 主循环流程

```
┌─────────────────────────────────────────────────────────────┐
│ AgentLoop.run() - 主循环                                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
    ┌──────────────────────────────────┐
    │ await bus.consume_inbound(1s)    │
    │ ├─ 有消息 → _process_message()   │
    │ └─ 超时 → continue              │
    └──────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ _process_message(InboundMessage)                            │
├─────────────────────────────────────────────────────────────┤
│ 1. 斜杠命令检测                                              │
│    ├─ /new → 触发整理 + 清空会话                            │
│    └─ /help → 返回帮助信息                                  │
│                                                              │
│ 2. 会话管理                                                  │
│    ├─ session = sessions.get_or_create(f"{channel}:{chat_id}")│
│    ├─ history = session.get_history(max_messages=100)       │
│    └─ 检查整理: if unconsolidated >= 100 → 后台整理          │
│                                                              │
│ 3. 上下文构建                                                │
│    └─ messages = context.build_messages(...)                │
│                                                              │
│ 4. LLM + 工具循环                                           │
│    └─ final_content = await _run_agent_loop(messages)       │
│                                                              │
│ 5. 会话保存                                                  │
│    ├─ session.messages.extend(new_messages)                 │
│    └─ sessions.save(session)                                │
│                                                              │
│ 6. 响应发送                                                  │
│    └─ if not message_tool._sent_in_turn:                    │
│       └─ bus.publish_outbound(OutboundMessage)              │
└─────────────────────────────────────────────────────────────┘
```

## 消息处理

### 斜杠命令

**位置**: `loop.py:296-323`

```python
# /new - 触发记忆整理并清空会话
if msg.content.strip() == "/new":
    # 强制整理所有消息
    await self._consolidate_memory(
        session=session,
        force_all=True  # 整理全部,不保留尾部
    )

    # 清空会话
    session.messages.clear()
    session.last_consolidated = 0
    self.sessions.save(session)

    return OutboundMessage(
        channel=msg.channel,
        chat_id=msg.chat_id,
        content="Session cleared. Memory consolidated."
    )

# /help - 返回帮助信息
if msg.content.strip() == "/help":
    return OutboundMessage(
        channel=msg.channel,
        chat_id=msg.chat_id,
        content=self._get_help_text()
    )
```

### 会话获取

**位置**: `loop.py:325-350`

```python
# 1. 获取或创建会话
session_key = msg.session_key  # 默认: f"{channel}:{chat_id}"
session = self.sessions.get_or_create(session_key)

# 2. 提取历史 (最近 max_messages 条)
history = session.get_history(
    max_messages=self.config.agent.max_history or 100
)

# 3. 检查是否需要整理
unconsolidated = len(session.messages) - session.last_consolidated
memory_window = self.config.agent.memory_window or 100

if unconsolidated >= memory_window:
    # 获取整理锁 (per-session)
    lock = self._get_consolidation_lock(session_key)

    if not lock.locked():
        # 后台异步整理,不阻塞当前消息
        task = asyncio.create_task(
            self._consolidate_memory(session)
        )
        # 添加清理回调
        task.add_done_callback(
            lambda _: self._prune_consolidation_lock(session_key, lock)
        )
```

## LLM 工具循环

**位置**: `loop.py:174-238`

### 核心循环

```python
async def _run_agent_loop(
    self,
    messages: list[dict],
    max_iterations: int = 40,
    on_progress: callable = None
) -> str:
    """
    LLM 调用与工具执行循环

    Args:
        messages: 包含 system + history + current 的完整消息列表
        max_iterations: 最大工具调用轮次 (防止无限循环)
        on_progress: 进度回调 (发送中间状态)

    Returns:
        最终响应文本
    """
    iteration = 0

    while iteration < max_iterations:
        # 1. 调用 LLM
        response = await self.provider.chat(
            messages=messages,
            tools=self.tools.get_definitions(),  # OpenAI function format
            model=self.config.agent.model,
            temperature=self.config.agent.temperature,
            max_tokens=self.config.agent.max_tokens
        )

        # 2. 检查工具调用
        if response.has_tool_calls:
            # 发送进度提示
            if on_progress and response.content:
                await on_progress(response.content)

            # 生成工具提示
            tool_names = [tc.name for tc in response.tool_calls]
            tool_hint = f"Using tools: {', '.join(tool_names)}"
            if on_progress:
                await on_progress(tool_hint, tool_hint=True)

            # 添加 assistant 消息
            messages.append({
                "role": "assistant",
                "content": response.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": json.dumps(tc.arguments)
                        }
                    }
                    for tc in response.tool_calls
                ],
                # Kimi/DeepSeek-R1 思维链
                **({"reasoning_content": response.reasoning_content}
                   if response.reasoning_content else {})
            })

            # 执行每个工具
            for tc in response.tool_calls:
                try:
                    result = await self.tools.execute(
                        tc.name,
                        tc.arguments
                    )

                    # 截断过长结果 (节省 token)
                    if len(result) > 500:
                        result = result[:500] + "\n... (truncated)"

                except Exception as e:
                    result = f"Error executing {tc.name}: {str(e)}"

                # 添加 tool 消息
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": tc.name,
                    "content": result
                })

            iteration += 1
            continue  # 回到 LLM

        else:
            # 无工具调用,返回最终响应
            return response.content or ""

    # 达到最大迭代次数
    logger.warning(f"Reached max iterations ({max_iterations})")
    return "Max iterations reached. Task may be incomplete."
```

### 进度回调

```python
# 在 _process_message 中创建进度回调
async def send_progress(content: str, tool_hint: bool = False):
    await self.bus.publish_outbound(
        OutboundMessage(
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=content,
            metadata={
                "_progress": not tool_hint,
                "_tool_hint": tool_hint
            }
        )
    )

# 传递给工具循环
final_content = await self._run_agent_loop(
    messages=messages,
    on_progress=send_progress
)
```

## 工具注册

**位置**: `loop.py:104-141`

### 默认工具集

```python
def __init__(self, ...):
    # 创建工具注册表
    self.tools = ToolRegistry()

    # 文件系统工具
    self.tools.register(ReadFileTool(workspace))
    self.tools.register(WriteFileTool(workspace))
    self.tools.register(EditFileTool(workspace))
    self.tools.register(ListDirTool(workspace))

    # Shell 执行
    self.tools.register(ExecTool(
        workspace=workspace,
        restrict_to_workspace=config.agent.restrict_to_workspace
    ))

    # Web 工具
    if config.web_search and config.web_search.brave_api_key:
        self.tools.register(WebSearchTool(config.web_search))
    self.tools.register(WebFetchTool())

    # Agent 通信工具
    self.message_tool = MessageTool(self.bus)
    self.tools.register(self.message_tool)

    # Subagent 工具
    self.tools.register(SpawnTool(self.subagent_manager))

    # Cron 工具 (可选)
    if config.cron and config.cron.enabled:
        self.tools.register(CronTool(self.cron_service))
```

### MCP 工具 (懒加载)

```python
async def _connect_mcp_if_needed(self):
    """首次消息时连接 MCP 服务器"""
    if self._mcp_connected:
        return

    for server_name, server_config in self.config.mcp_servers.items():
        try:
            client = MCPClient(server_config)
            await client.connect()

            # 动态注册 MCP 工具
            for tool_def in client.list_tools():
                self.tools.register(
                    MCPTool(client, tool_def)
                )

            logger.info(f"MCP server {server_name} connected")
        except Exception as e:
            logger.error(f"MCP {server_name} failed: {e}")

    self._mcp_connected = True
```

## 会话管理

### 会话保存

**位置**: `loop.py:403-423`

```python
# 1. 提取本轮新增消息
new_messages = messages[len(history):]

# 2. 添加时间戳并截断过长工具结果
for msg in new_messages:
    if msg["role"] == "tool" and len(msg["content"]) > 500:
        msg["content"] = msg["content"][:500] + "\n... (truncated)"

    msg["timestamp"] = datetime.now().isoformat()

# 3. 追加到会话
session.messages.extend(new_messages)
session.updated_at = datetime.now()

# 4. 持久化到 JSONL
self.sessions.save(session)
```

### Message Tool 检查

```python
# 检查是否使用了 message 工具
if self.message_tool._sent_in_turn:
    # 工具已发送消息,不重复发送
    self.message_tool._sent_in_turn = False  # 重置标志
    return None

# 正常发送响应
return OutboundMessage(
    channel=msg.channel,
    chat_id=msg.chat_id,
    content=final_content
)
```

## 记忆整理触发

**位置**: `loop.py:363-395`

### 触发条件

```python
unconsolidated_count = len(session.messages) - session.last_consolidated

if unconsolidated_count >= memory_window:  # 默认 100
    # 后台异步整理
    lock = self._get_consolidation_lock(session_key)

    if not lock.locked():  # 避免并发整理
        task = asyncio.create_task(
            self._consolidate_memory(session)
        )
        task.add_done_callback(
            lambda _: self._prune_consolidation_lock(session_key, lock)
        )
```

### 并发控制

```python
# 每个 session 独立锁
self._consolidation_locks: dict[str, asyncio.Lock] = {}

def _get_consolidation_lock(self, session_key: str) -> asyncio.Lock:
    lock = self._consolidation_locks.get(session_key)
    if lock is None:
        lock = asyncio.Lock()
        self._consolidation_locks[session_key] = lock
    return lock

def _prune_consolidation_lock(self, session_key: str, lock: asyncio.Lock):
    """清理未锁定的锁对象"""
    if not lock.locked():
        self._consolidation_locks.pop(session_key, None)
```

### 整理流程

```python
async def _consolidate_memory(
    self,
    session: Session,
    force_all: bool = False
):
    """
    后台记忆整理

    Args:
        session: 要整理的会话
        force_all: 是否整理所有消息 (/new 命令)
    """
    # 1. 获取锁
    lock = self._get_consolidation_lock(session.key)
    async with lock:
        # 2. 委托给 MemoryStore
        await self.memory.consolidate(
            session=session,
            force_all=force_all,
            provider=self.provider,
            config=self.config
        )

        # 3. 保存会话 (更新 last_consolidated)
        self.sessions.save(session)
```

## 关键代码位置

| 功能 | 文件 | 行号 |
|------|------|------|
| 主循环 | `loop.py` | 34-89 |
| 消息处理 | `loop.py` | 296-423 |
| LLM 工具循环 | `loop.py` | 174-238 |
| 工具注册 | `loop.py` | 104-141 |
| 记忆整理触发 | `loop.py` | 363-395 |
| 进度回调 | `loop.py` | 240-260 |
| 斜杠命令 | `loop.py` | 296-323 |

## 扩展点

### 1. 自定义工具

```python
# 创建自定义工具
class MyTool(Tool):
    name = "my_tool"
    description = "My custom tool"

    def get_definition(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {...}
            }
        }

    async def execute(self, **kwargs) -> str:
        # 工具逻辑
        return "Result"

# 注册到 AgentLoop
agent_loop.tools.register(MyTool())
```

### 2. 自定义斜杠命令

```python
# 在 _process_message 中添加
if msg.content.startswith("/my_command"):
    # 处理自定义命令
    return OutboundMessage(...)
```

### 3. 调整迭代限制

```python
# 配置文件
{
  "agent": {
    "max_iterations": 60,  # 增加到 60 轮
    "max_history": 200,    # 增加历史窗口
    "memory_window": 150   # 调整整理阈值
  }
}
```

## 性能考虑

1. **工具结果截断**: 超过 500 字符自动截断,节省 token
2. **异步整理**: 记忆整理不阻塞当前消息处理
3. **Session 缓存**: SessionManager 内存缓存避免重复读取
4. **Prompt Caching**: 支持 Anthropic/OpenRouter 缓存 (Provider 层)

## 下一步

- 了解 [MessageBus](./message-bus.md) 如何路由消息
- 学习 [ContextBuilder](../03-infrastructure/context-building.md) 如何组装上下文
- 查看 [MemoryStore](../02-advanced-features/memory-consolidation.md) 整理机制

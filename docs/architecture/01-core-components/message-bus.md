# MessageBus - 异步消息总线

## 概述

**文件**: `nanobot/bus/queue.py:8-45`, `nanobot/bus/events.py`

MessageBus 是 nanobot 的核心通信组件,基于 Python asyncio.Queue 实现进程内异步消息队列。

## 核心设计

### 双队列架构

```python
class MessageBus:
    def __init__(self):
        self.inbound = asyncio.Queue()   # Channel → Agent
        self.outbound = asyncio.Queue()  # Agent → Channel
```

**流向**:
```
Channel → inbound → Agent → outbound → Channel
```

## 消息类型

### InboundMessage (入站消息)

**文件**: `nanobot/bus/events.py`

```python
@dataclass
class InboundMessage:
    channel: str              # 来源平台: "telegram", "discord", ...
    sender_id: str            # 发送者ID
    chat_id: str              # 会话ID
    content: str              # 文本内容
    media: list[str] = []     # 媒体文件路径列表
    timestamp: datetime = field(default_factory=datetime.now)
    session_key_override: str | None = None  # 可选: 自定义 session key

    @property
    def session_key(self) -> str:
        """会话唯一标识符"""
        return self.session_key_override or f"{self.channel}:{self.chat_id}"
```

**用途**:
- Channel 封装用户消息
- 包含媒体文件路径 (已下载到本地)
- 支持自定义 session key (如 Slack threads)

### OutboundMessage (出站消息)

```python
@dataclass
class OutboundMessage:
    channel: str              # 目标平台
    chat_id: str              # 目标会话ID
    content: str              # 文本内容
    media: list[str] = []     # 可选: 媒体文件URL
    metadata: dict[str, Any] = field(default_factory=dict)

    # 常用 metadata 字段:
    # - "_progress": bool       # 是否为进度消息
    # - "_tool_hint": bool      # 是否为工具提示
    # - "thread_ts": str        # Slack thread 时间戳
```

**用途**:
- Agent 封装响应消息
- ChannelManager 路由到对应平台
- metadata 控制特殊行为 (进度消息过滤等)

## 核心方法

### 发布消息

```python
async def publish_inbound(self, msg: InboundMessage):
    """Channel 发布入站消息"""
    await self.inbound.put(msg)

async def publish_outbound(self, msg: OutboundMessage):
    """Agent 发布出站消息"""
    await self.outbound.put(msg)
```

### 消费消息

```python
async def consume_inbound(self, timeout: float | None = None) -> InboundMessage | None:
    """
    Agent 消费入站消息

    Args:
        timeout: 超时时间 (秒), None 表示阻塞等待

    Returns:
        InboundMessage 或 None (超时)

    Raises:
        asyncio.TimeoutError: 超时
    """
    if timeout is None:
        return await self.inbound.get()
    else:
        return await asyncio.wait_for(
            self.inbound.get(),
            timeout=timeout
        )

async def consume_outbound(self) -> OutboundMessage:
    """ChannelManager 消费出站消息 (阻塞)"""
    return await self.outbound.get()
```

## 使用模式

### Channel 发布入站消息

```python
# 在 Channel._handle_message() 中
async def _handle_message(self, update):
    # 1. 权限检查
    if not self.is_allowed(sender_id):
        return

    # 2. 下载媒体
    media_paths = []
    for media_obj in update.media:
        path = await self._download_media(media_obj)
        media_paths.append(str(path))

    # 3. 创建入站消息
    msg = InboundMessage(
        channel=self.name,
        sender_id=str(update.sender.id),
        chat_id=str(update.chat.id),
        content=update.text,
        media=media_paths
    )

    # 4. 发布到总线
    await self.bus.publish_inbound(msg)
```

### Agent 轮询入站消息

```python
# 在 AgentLoop.run() 中
async def run(self):
    while True:
        try:
            # 1秒超时轮询
            msg = await self.bus.consume_inbound(timeout=1.0)

            if msg:
                # 处理消息
                response = await self._process_message(msg)

                if response:
                    # 发布出站消息
                    await self.bus.publish_outbound(response)

        except asyncio.TimeoutError:
            # 超时继续循环
            continue
```

### ChannelManager 路由出站消息

```python
# 在 ChannelManager._dispatch_outbound() 中
async def _dispatch_outbound(self):
    """消费出站队列并路由到对应 Channel"""
    while True:
        # 阻塞等待
        msg = await self.bus.consume_outbound()

        # 过滤进度消息
        if msg.metadata.get("_progress"):
            if not self.config.send_progress:
                continue

        if msg.metadata.get("_tool_hint"):
            if not self.config.send_tool_hints:
                continue

        # 路由到对应 Channel
        channel = self.channels.get(msg.channel)
        if channel:
            await channel.send(msg)
        else:
            logger.warning(f"Unknown channel: {msg.channel}")
```

## 数据流可视化

```
┌─────────────────────────────────────────────────────────────┐
│                    User Input                                │
│         (Telegram/Discord/Slack/Email/...)                  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ Channel._handle_message()                                    │
│ ├─ Permission check                                          │
│ ├─ Download media                                            │
│ └─ Create InboundMessage                                     │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ MessageBus.publish_inbound(msg)                              │
│ └─ inbound.put(msg)                                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ AgentLoop.run()                                              │
│ └─ msg = await bus.consume_inbound(timeout=1s)              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ AgentLoop._process_message(msg)                              │
│ ├─ LLM + Tools loop                                          │
│ └─ Create OutboundMessage                                    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ MessageBus.publish_outbound(response)                        │
│ └─ outbound.put(response)                                    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ ChannelManager._dispatch_outbound()                          │
│ ├─ msg = await bus.consume_outbound()                        │
│ ├─ Filter progress messages                                  │
│ └─ channel.send(msg)                                         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                    User Receives Response                     │
└─────────────────────────────────────────────────────────────┘
```

## 特殊消息类型

### 进度消息

Agent 发送中间进度:

```python
# Agent 发送进度
await bus.publish_outbound(
    OutboundMessage(
        channel="telegram",
        chat_id="123456",
        content="Processing your request...",
        metadata={"_progress": True}
    )
)

# ChannelManager 根据配置过滤
if msg.metadata.get("_progress") and not config.send_progress:
    continue  # 跳过发送
```

### 工具提示

Agent 提示工具使用:

```python
await bus.publish_outbound(
    OutboundMessage(
        channel="telegram",
        chat_id="123456",
        content="Using tools: read_file, exec",
        metadata={"_tool_hint": True}
    )
)
```

### 系统消息 (Subagent 结果)

Subagent 完成后注入系统消息:

```python
# Subagent 完成
await bus.publish_inbound(
    InboundMessage(
        channel="system",
        sender_id="subagent",
        chat_id=f"{origin_channel}:{origin_chat_id}",
        content=f"[Subagent '{label}' completed]\n\n{result}"
    )
)

# Agent 检测并处理
if msg.channel == "system":
    # 解析原始 channel/chat_id
    # 使用原会话历史生成用户友好的摘要
```

## 优势

### 1. 零外部依赖

- 基于 Python 标准库 asyncio.Queue
- 无需 Redis, RabbitMQ, Kafka 等外部消息队列
- 单进程部署,简化运维

### 2. 低延迟

- 进程内通信,无网络开销
- 异步非阻塞,高效并发

### 3. 自然背压

- Queue 满时自动阻塞生产者
- 避免内存溢出

### 4. 类型安全

- Pydantic dataclass 强类型检查
- IDE 智能提示

## 限制

### 1. 单进程

- 不支持分布式部署
- 无法跨机器通信

### 2. 非持久化

- 消息仅在内存中
- 进程重启丢失队列中的消息

### 3. 无优先级

- FIFO 顺序,无法插队
- 所有消息平等处理

## 扩展点

### 1. 持久化消息队列

替换为 Redis/RabbitMQ:

```python
class RedisBus:
    async def publish_inbound(self, msg: InboundMessage):
        await redis.lpush("nanobot:inbound", msg.json())

    async def consume_inbound(self, timeout: float):
        result = await redis.brpop("nanobot:inbound", timeout=timeout)
        if result:
            return InboundMessage.parse_raw(result[1])
```

### 2. 优先级队列

```python
class PriorityBus:
    def __init__(self):
        self.inbound = asyncio.PriorityQueue()

    async def publish_inbound(self, msg: InboundMessage, priority: int = 5):
        await self.inbound.put((priority, msg))

    async def consume_inbound(self):
        priority, msg = await self.inbound.get()
        return msg
```

### 3. 消息持久化日志

记录所有消息用于调试:

```python
class LoggingBus(MessageBus):
    async def publish_inbound(self, msg: InboundMessage):
        # 记录到文件
        with open("message_log.jsonl", "a") as f:
            f.write(msg.json() + "\n")

        await super().publish_inbound(msg)
```

## 下一步

- 了解 [AgentLoop](./agent-loop.md) 如何消费消息
- 查看 [ChannelManager](./channel-system.md) 如何路由消息
- 学习 [SubagentSystem](../02-advanced-features/subagent-system.md) 如何使用系统消息

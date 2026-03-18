# Memory Consolidation - 记忆整理系统

## 概述

**文件**: `nanobot/agent/memory.py:18-151`

Nanobot 实现了双层记忆架构 + LLM 驱动的自动整理机制,能够智能提炼对话历史为长期知识。

## 双层记忆架构

### MEMORY.md (长期事实库)

**位置**: `workspace/memory/MEMORY.md`

**特点**:
- 完全重写更新
- 存储长期事实和知识
- 每次请求注入到 system prompt

**格式**:
```markdown
# Memory

## User Preferences
- 喜欢简洁的代码风格
- 使用 Python 3.10+ 特性

## Project Information
- 项目名称: nanobot
- 技术栈: Python, asyncio, LiteLLM

## Context
- 当前在开发记忆整理功能
- 使用 JSONL 格式持久化会话
```

### HISTORY.md (事件日志)

**位置**: `workspace/memory/HISTORY.md`

**特点**:
- 追加写入
- 时间戳日志格式
- 用于 grep 搜索历史事件

**格式**:
```
[2026-03-18 16:30] 用户询问了 nanobot 架构,我解释了消息驱动 + 事件总线模式,使用了 read_file 和 grep 工具查看代码。

[2026-03-18 17:15] 用户请求创建架构文档,我使用 write_file 工具创建了 docs/architecture/ 目录结构。

[2026-03-19 10:00] 用户报告了 Telegram 连接问题,我检查了配置文件并修复了 API token 错误。
```

## 触发机制

### 触发条件

**位置**: `nanobot/agent/loop.py:363-380`

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

**条件**:
1. 未整理消息数 ≥ memory_window (默认 100)
2. 该 session 未在整理中 (通过锁控制)

**特点**:
- **异步非阻塞**: 使用 `asyncio.create_task` 后台执行
- **Per-Session 锁**: 每个会话独立锁,避免并发整理同一会话
- **自动清理**: 完成后清理锁对象

### 手动触发

```python
# /new 命令强制整理所有消息
if msg.content.strip() == "/new":
    await self._consolidate_memory(
        session=session,
        force_all=True  # 整理全部,不保留尾部
    )

    # 清空会话
    session.messages.clear()
    session.last_consolidated = 0
```

## 整理流程

### 完整流程

**位置**: `nanobot/agent/memory.py:69-150`

```
1. 提取旧消息
   ├─ 正常整理: messages[last_consolidated : -keep_count]
   │   └─ keep_count = memory_window // 2 (保留最近 50 条)
   └─ 全部整理 (/new): 所有消息

2. 格式化为时间戳日志
   [2026-03-18 16:30] USER: 用户消息
   [2026-03-18 16:31] ASSISTANT [tools: read_file, exec]: 助手响应
   [2026-03-18 16:31] TOOL(read_file): 工具结果 (截断)

3. 读取当前长期记忆
   current_memory = read_long_term() → MEMORY.md

4. 调用 LLM + save_memory 工具
   messages = [
     {role: "system", content: "You are a memory consolidation agent..."},
     {role: "user", content: "## Current Memory\n{current_memory}\n\n## Conversation\n{formatted}"}
   ]

5. LLM 返回工具调用
   {
     "history_entry": "[2026-03-18 16:30] 用户询问了XXX,完成了YYY",
     "memory_update": "# Memory\n\n## User Preferences\n- ...\n\n## Project\n- ..."
   }

6. 原子写入
   ├─ append_history(history_entry) → HISTORY.md
   └─ write_long_term(memory_update) → MEMORY.md

7. 更新检查点
   session.last_consolidated = len(session.messages) - keep_count
```

### 代码实现

```python
async def consolidate(
    self,
    session: Session,
    force_all: bool = False,
    provider: LLMProvider,
    config: Config
):
    """
    后台记忆整理

    Args:
        session: 要整理的会话
        force_all: 是否整理所有消息 (/new 命令)
        provider: LLM 提供商
        config: 配置对象
    """
    # 1. 提取旧消息
    if force_all:
        old_messages = session.messages
        keep_count = 0
    else:
        keep_count = (config.agent.memory_window or 100) // 2
        old_messages = session.messages[
            session.last_consolidated : -keep_count if keep_count > 0 else None
        ]

    if not old_messages:
        return  # 无需整理

    # 2. 格式化为时间戳日志
    formatted = self._format_messages(old_messages)

    # 3. 读取当前长期记忆
    current_memory = self.read_long_term()

    # 4. 构建 LLM 消息
    consolidation_prompt = f"""Process the following conversation and update the memory.

## Current Memory
{current_memory}

## Conversation to Consolidate
{formatted}

Use the save_memory tool to:
1. Create a concise history_entry (2-5 sentences) summarizing key events
2. Update memory_update with all existing facts plus new information
"""

    messages = [
        {"role": "system", "content": "You are a memory consolidation agent."},
        {"role": "user", "content": consolidation_prompt}
    ]

    # 5. 调用 LLM
    response = await provider.chat(
        messages=messages,
        tools=[self._get_save_memory_tool()],
        model=config.agent.model,
        temperature=0.3  # 较低温度,保证一致性
    )

    # 6. 解析工具调用
    if not response.has_tool_calls:
        logger.warning("LLM did not call save_memory tool")
        return

    tool_call = response.tool_calls[0]
    args = tool_call.arguments

    # Provider 兼容性处理
    if isinstance(args, str):
        args = json.loads(args)

    history_entry = args.get("history_entry", "")
    memory_update = args.get("memory_update", "")

    # 处理非字符串值
    if not isinstance(history_entry, str):
        history_entry = json.dumps(history_entry, ensure_ascii=False)
    if not isinstance(memory_update, str):
        memory_update = json.dumps(memory_update, ensure_ascii=False)

    # 7. 原子写入
    self.append_history(history_entry)
    self.write_long_term(memory_update)

    # 8. 更新检查点
    session.last_consolidated = len(session.messages) - keep_count
```

## save_memory 工具定义

**位置**: `nanobot/agent/memory.py:18-42`

```python
def _get_save_memory_tool() -> dict:
    return {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "Save memory consolidation result",
            "parameters": {
                "type": "object",
                "properties": {
                    "history_entry": {
                        "type": "string",
                        "description": """A paragraph (2-5 sentences) summarizing key events from this conversation.
Start with timestamp: [YYYY-MM-DD HH:MM]
Focus on: what the user wanted, what was accomplished, tools used."""
                    },
                    "memory_update": {
                        "type": "string",
                        "description": """Full updated long-term memory as markdown.
Must include:
- All existing facts from current memory
- New information from this conversation
- Organized in clear sections (User Preferences, Project, Context, etc.)"""
                    }
                },
                "required": ["history_entry", "memory_update"]
            }
        }
    }
```

## 消息格式化

### 格式化规则

```python
def _format_messages(self, messages: list[dict]) -> str:
    """
    格式化消息为时间戳日志

    输入:
      [
        {role: "user", content: "Hello", timestamp: "2026-03-18T16:30:00"},
        {role: "assistant", content: "Hi", tool_calls: [...], timestamp: "..."},
        {role: "tool", name: "read_file", content: "...", timestamp: "..."}
      ]

    输出:
      [2026-03-18 16:30] USER: Hello
      [2026-03-18 16:31] ASSISTANT [tools: read_file]: Hi
      [2026-03-18 16:31] TOOL(read_file): ... (truncated)
    """
    lines = []

    for msg in messages:
        timestamp = msg.get("timestamp", "")
        if timestamp:
            ts = datetime.fromisoformat(timestamp).strftime("%Y-%m-%d %H:%M")
        else:
            ts = "Unknown Time"

        role = msg.get("role", "").upper()
        content = msg.get("content", "")

        # 截断过长内容
        if len(content) > 500:
            content = content[:500] + "... (truncated)"

        # 工具调用提示
        if role == "ASSISTANT" and "tool_calls" in msg:
            tool_names = [tc["function"]["name"] for tc in msg["tool_calls"]]
            tools_str = ", ".join(tool_names)
            lines.append(f"[{ts}] {role} [tools: {tools_str}]: {content}")

        # 工具结果
        elif role == "TOOL":
            tool_name = msg.get("name", "unknown")
            lines.append(f"[{ts}] {role}({tool_name}): {content}")

        # 普通消息
        else:
            lines.append(f"[{ts}] {role}: {content}")

    return "\n".join(lines)
```

## 持久化操作

### 读取长期记忆

```python
def read_long_term(self) -> str:
    """读取 MEMORY.md"""
    memory_file = self.workspace / "memory" / "MEMORY.md"

    if not memory_file.exists():
        return ""

    return memory_file.read_text(encoding="utf-8")
```

### 写入长期记忆

```python
def write_long_term(self, content: str):
    """完全重写 MEMORY.md"""
    memory_file = self.workspace / "memory" / "MEMORY.md"
    memory_file.parent.mkdir(parents=True, exist_ok=True)

    # 原子写入: 先写临时文件,再重命名
    tmp_file = memory_file.with_suffix(".tmp")
    tmp_file.write_text(content, encoding="utf-8")
    tmp_file.replace(memory_file)
```

### 追加历史日志

```python
def append_history(self, entry: str):
    """追加到 HISTORY.md"""
    history_file = self.workspace / "memory" / "HISTORY.md"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    # 追加模式
    with history_file.open("a", encoding="utf-8") as f:
        f.write(entry + "\n\n")
```

## 与上下文系统集成

### 注入到 System Prompt

**位置**: `nanobot/agent/context.py:56-71`

```python
def build_system_prompt(self, skill_names: list[str] | None = None) -> str:
    parts = []

    # ... Identity, Bootstrap ...

    # Memory Context
    memory = self.memory.get_memory_context()
    if memory:
        parts.append(f"# Memory\n\n{memory}")

    # ... Skills ...

    return "\n\n---\n\n".join(parts)
```

### get_memory_context()

```python
def get_memory_context(self) -> str:
    """
    获取记忆上下文 (用于注入 system prompt)

    Returns:
        MEMORY.md 内容,如果为空则返回空字符串
    """
    content = self.read_long_term()
    return content.strip()
```

## 并发控制

### Per-Session 锁

**位置**: `nanobot/agent/loop.py:284-295`

```python
# 每个 session 独立锁
self._consolidation_locks: dict[str, asyncio.Lock] = {}

def _get_consolidation_lock(self, session_key: str) -> asyncio.Lock:
    """获取或创建整理锁"""
    lock = self._consolidation_locks.get(session_key)
    if lock is None:
        lock = asyncio.Lock()
        self._consolidation_locks[session_key] = lock
    return lock

def _prune_consolidation_lock(self, session_key: str, lock: asyncio.Lock):
    """清理未锁定的锁对象 (避免内存泄漏)"""
    if not lock.locked():
        self._consolidation_locks.pop(session_key, None)
```

### 使用模式

```python
lock = self._get_consolidation_lock(session_key)

if not lock.locked():  # 避免重复整理
    task = asyncio.create_task(
        self._consolidate_memory(session)
    )

    # 完成后清理锁
    task.add_done_callback(
        lambda _: self._prune_consolidation_lock(session_key, lock)
    )
```

## 配置选项

```json
{
  "agent": {
    "memory_window": 100,  // 整理阈值 (未整理消息数)
    "model": "claude-opus-4",  // 用于整理的模型
    "temperature": 0.3  // 较低温度,保证一致性
  }
}
```

## 最佳实践

### 1. MEMORY.md 组织结构

推荐使用清晰的 Markdown 结构:

```markdown
# Memory

## User Preferences
- 编程风格: 简洁, PEP 8
- 语言: 中文为主,技术术语英文
- 交互: 提供代码示例和可视化

## Current Project
- 名称: nanobot
- 技术栈: Python 3.10+, asyncio, LiteLLM
- 架构: 消息驱动 + 事件总线

## Context
- 当前任务: 创建架构文档
- 进度: 已完成核心组件文档
- 下一步: 扩展开发指南

## Known Issues
- Telegram 长轮询偶尔超时 → 已添加重试机制
- Memory consolidation 有时遗漏细节 → 调整 prompt
```

### 2. history_entry 编写

- 以时间戳开头: `[2026-03-18 16:30]`
- 2-5 句话概括
- 包含: 用户需求 + 完成内容 + 使用工具

示例:
```
[2026-03-18 16:30] 用户询问了 nanobot 的完整架构,我使用 read_file 和 grep 工具探索了所有核心模块,解释了消息驱动 + 事件总线模式,并创建了 docs/architecture/ 目录结构和架构文档。
```

### 3. memory_update 编写

- 包含所有旧事实 (不能丢失信息)
- 添加新事实
- 保持组织结构一致

## 性能考虑

1. **异步非阻塞**: 整理不阻塞当前消息处理
2. **保留尾部消息**: 保留最近 50 条消息避免重复整理
3. **截断长内容**: 格式化时截断 > 500 字符的内容
4. **原子写入**: 使用临时文件 + rename 避免部分写入
5. **Per-Session 锁**: 避免并发整理同一会话

## 扩展点

### 1. 增量更新策略

当前: 完全重写 MEMORY.md
扩展: 仅存储 diff

```python
{
  "memory_changes": [
    {"op": "add", "path": "/user_preferences/style", "value": "简洁"},
    {"op": "remove", "path": "/old_project"}
  ]
}
```

### 2. 压缩旧记忆

多轮整理后,压缩历史记忆:

```python
async def compress_old_memory(self):
    old_memory = self.read_long_term()

    # 使用 LLM 压缩
    compressed = await llm_compress(old_memory)

    self.write_long_term(compressed)
```

### 3. 向量搜索

集成向量数据库检索相关记忆:

```python
class VectorMemoryStore:
    async def search(self, query: str, top_k: int = 5) -> list[str]:
        # 向量检索相关记忆片段
        return relevant_memories
```

### 4. 多层存储

```
MEMORY.md (热数据,最近 1000 条)
ARCHIVE.md (冷数据,历史 > 1000 条)
```

## 下一步

- 了解 [Session 管理](./session-management.md) 如何触发整理
- 查看 [Context 构建](../03-infrastructure/context-building.md) 如何注入记忆
- 学习 [Skills 加载](./skills-loading.md) 三级策略

# 添加自定义工具

本指南介绍如何为 nanobot 开发自定义工具,扩展 Agent 的能力。

## 概述

工具 (Tool) 是 Agent 与外部系统交互的接口。通过 OpenAI Function Calling 格式,LLM 可以决策调用工具并传递参数。

## 工具系统架构

```
ToolRegistry
  ├─ _tools: dict[str, Tool]
  ├─ register(tool: Tool)
  ├─ get_definitions() → list[dict]  # OpenAI function format
  └─ execute(name, params) → str

Tool (抽象基类)
  ├─ name: str
  ├─ description: str
  ├─ get_definition() → dict
  ├─ validate_params(params) → list[str] | None
  └─ execute(**kwargs) → str
```

## 快速开始

### 1. 创建工具类

```python
from nanobot.agent.tools.base import Tool

class WeatherTool(Tool):
    """查询天气信息"""

    name = "weather"
    description = "Get current weather for a location"

    def get_definition(self) -> dict:
        """返回 OpenAI function format"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City name, e.g., 'Beijing', 'New York'"
                        },
                        "unit": {
                            "type": "string",
                            "enum": ["celsius", "fahrenheit"],
                            "description": "Temperature unit",
                            "default": "celsius"
                        }
                    },
                    "required": ["location"]
                }
            }
        }

    async def execute(self, location: str, unit: str = "celsius") -> str:
        """执行工具逻辑"""
        # 1. 调用天气 API
        weather_data = await self._fetch_weather(location)

        # 2. 格式化结果
        temp = weather_data["temp"]
        if unit == "fahrenheit":
            temp = temp * 9/5 + 32

        return f"Weather in {location}: {temp}°{unit[0].upper()}, {weather_data['description']}"

    async def _fetch_weather(self, location: str) -> dict:
        """调用外部 API"""
        # 示例: 使用 httpx
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.weather.com/current",
                params={"q": location}
            )
            return response.json()
```

### 2. 注册工具

在 `nanobot/agent/loop.py` 的 `__init__` 方法中:

```python
# 在工具注册部分
self.tools.register(WeatherTool())
```

或者,通过配置动态加载:

```python
# config.json
{
  "agent": {
    "custom_tools": [
      "myproject.tools.WeatherTool"
    ]
  }
}

# 在 AgentLoop 中
for tool_path in config.agent.custom_tools:
    module_name, class_name = tool_path.rsplit(".", 1)
    module = importlib.import_module(module_name)
    tool_class = getattr(module, class_name)
    self.tools.register(tool_class())
```

### 3. 测试工具

```python
# 手动测试
tool = WeatherTool()
result = await tool.execute(location="Beijing", unit="celsius")
print(result)

# LLM 测试
# Agent 会自动根据用户消息决策是否调用工具
# 用户: "What's the weather in Beijing?"
# Agent: [调用 weather tool] → [返回结果]
```

## Tool 抽象基类

**文件**: `nanobot/agent/tools/base.py:7-103`

```python
from abc import ABC, abstractmethod

class Tool(ABC):
    """工具抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称 (唯一标识符)"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """工具功能描述 (用于 LLM 理解)"""
        pass

    @abstractmethod
    def get_definition(self) -> dict:
        """
        返回 OpenAI Function Calling 格式定义

        Returns:
            {
              "type": "function",
              "function": {
                "name": "tool_name",
                "description": "...",
                "parameters": {
                  "type": "object",
                  "properties": {...},
                  "required": [...]
                }
              }
            }
        """
        pass

    def validate_params(self, params: dict) -> list[str] | None:
        """
        验证参数 (可选)

        Args:
            params: LLM 传递的参数

        Returns:
            None 表示验证通过
            list[str] 表示错误列表
        """
        # 基类默认使用 JSON Schema 验证
        definition = self.get_definition()
        schema = definition["function"]["parameters"]

        errors = []

        # 检查必需参数
        required = schema.get("required", [])
        for field in required:
            if field not in params:
                errors.append(f"Missing required parameter: {field}")

        # 检查类型
        properties = schema.get("properties", {})
        for field, value in params.items():
            if field not in properties:
                errors.append(f"Unknown parameter: {field}")
                continue

            field_schema = properties[field]
            expected_type = field_schema.get("type")

            # 简单类型检查
            if expected_type == "string" and not isinstance(value, str):
                errors.append(f"{field} must be string")
            elif expected_type == "number" and not isinstance(value, (int, float)):
                errors.append(f"{field} must be number")
            # ... 更多类型检查

        return errors if errors else None

    @abstractmethod
    async def execute(self, **kwargs) -> str:
        """
        执行工具逻辑

        Args:
            **kwargs: LLM 传递的参数 (已验证)

        Returns:
            工具执行结果 (字符串)

        Raises:
            Exception: 执行失败时抛出异常
        """
        pass
```

## 参数定义最佳实践

### 1. 清晰的描述

```python
"parameters": {
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "Absolute path to the file, e.g., '/home/user/file.txt'"
        },
        "content": {
            "type": "string",
            "description": "Content to write to the file"
        },
        "mode": {
            "type": "string",
            "enum": ["overwrite", "append"],
            "description": "Write mode: 'overwrite' replaces file, 'append' adds to end",
            "default": "overwrite"
        }
    },
    "required": ["file_path", "content"]
}
```

### 2. 使用 enum 限制选项

```python
"status": {
    "type": "string",
    "enum": ["pending", "in_progress", "completed"],
    "description": "Task status"
}
```

### 3. 提供默认值

```python
"timeout": {
    "type": "number",
    "description": "Request timeout in seconds",
    "default": 30
}
```

### 4. 嵌套对象

```python
"filters": {
    "type": "object",
    "properties": {
        "date_from": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
        "date_to": {"type": "string", "description": "End date (YYYY-MM-DD)"},
        "status": {"type": "string", "enum": ["open", "closed"]}
    }
}
```

### 5. 数组参数

```python
"tags": {
    "type": "array",
    "items": {"type": "string"},
    "description": "List of tags to filter by"
}
```

## 实际示例

### 示例 1: 数据库查询工具

```python
class DatabaseTool(Tool):
    """执行 SQL 查询"""

    name = "database_query"
    description = "Execute SQL query on the database"

    def __init__(self, db_url: str):
        self.db_url = db_url
        self.engine = create_async_engine(db_url)

    def get_definition(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "SQL query to execute (SELECT only)"
                        },
                        "limit": {
                            "type": "number",
                            "description": "Maximum rows to return",
                            "default": 100
                        }
                    },
                    "required": ["query"]
                }
            }
        }

    async def execute(self, query: str, limit: int = 100) -> str:
        # 安全检查: 仅允许 SELECT
        if not query.strip().upper().startswith("SELECT"):
            return "Error: Only SELECT queries are allowed"

        async with self.engine.connect() as conn:
            result = await conn.execute(text(query))
            rows = result.fetchmany(limit)

            # 格式化为 Markdown 表格
            if not rows:
                return "No results found"

            columns = result.keys()
            table = "| " + " | ".join(columns) + " |\n"
            table += "| " + " | ".join(["---"] * len(columns)) + " |\n"

            for row in rows:
                table += "| " + " | ".join(str(v) for v in row) + " |\n"

            return table
```

### 示例 2: Slack 消息工具

```python
class SlackTool(Tool):
    """发送 Slack 消息"""

    name = "slack_message"
    description = "Send a message to a Slack channel"

    def __init__(self, bot_token: str):
        self.client = WebClient(token=bot_token)

    def get_definition(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "channel": {
                            "type": "string",
                            "description": "Channel ID or name (e.g., '#general', 'C1234567890')"
                        },
                        "text": {
                            "type": "string",
                            "description": "Message text (supports mrkdwn)"
                        },
                        "thread_ts": {
                            "type": "string",
                            "description": "Thread timestamp to reply to (optional)"
                        }
                    },
                    "required": ["channel", "text"]
                }
            }
        }

    async def execute(self, channel: str, text: str, thread_ts: str | None = None) -> str:
        try:
            response = await asyncio.to_thread(
                self.client.chat_postMessage,
                channel=channel,
                text=text,
                thread_ts=thread_ts
            )

            return f"Message sent to {channel} (ts: {response['ts']})"
        except SlackApiError as e:
            return f"Error sending message: {e.response['error']}"
```

### 示例 3: GitHub 工具

```python
class GitHubTool(Tool):
    """GitHub 仓库操作"""

    name = "github"
    description = "Interact with GitHub repositories"

    def __init__(self, token: str):
        self.token = token

    def get_definition(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["create_issue", "list_prs", "get_commits"],
                            "description": "Action to perform"
                        },
                        "repo": {
                            "type": "string",
                            "description": "Repository in format 'owner/repo'"
                        },
                        "title": {
                            "type": "string",
                            "description": "Issue/PR title (for create_issue)"
                        },
                        "body": {
                            "type": "string",
                            "description": "Issue/PR body (for create_issue)"
                        }
                    },
                    "required": ["action", "repo"]
                }
            }
        }

    async def execute(self, action: str, repo: str, **kwargs) -> str:
        if action == "create_issue":
            return await self._create_issue(repo, kwargs["title"], kwargs["body"])
        elif action == "list_prs":
            return await self._list_prs(repo)
        elif action == "get_commits":
            return await self._get_commits(repo)

    async def _create_issue(self, repo: str, title: str, body: str) -> str:
        url = f"https://api.github.com/repos/{repo}/issues"
        headers = {"Authorization": f"token {self.token}"}
        data = {"title": title, "body": body}

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=data)
            issue = response.json()
            return f"Created issue #{issue['number']}: {issue['html_url']}"

    # ... 其他方法
```

## 工具注册

### 静态注册

在 `AgentLoop.__init__` 中:

```python
def __init__(self, ...):
    self.tools = ToolRegistry()

    # 内置工具
    self.tools.register(ReadFileTool(workspace))
    self.tools.register(WriteFileTool(workspace))

    # 自定义工具
    if config.database:
        self.tools.register(DatabaseTool(config.database.url))

    if config.slack:
        self.tools.register(SlackTool(config.slack.bot_token))
```

### 动态加载

通过配置文件:

```json
{
  "agent": {
    "custom_tools": [
      {
        "class": "myproject.tools.WeatherTool",
        "config": {"api_key": "${WEATHER_API_KEY}"}
      },
      {
        "class": "myproject.tools.DatabaseTool",
        "config": {"db_url": "postgresql://..."}
      }
    ]
  }
}
```

加载逻辑:

```python
for tool_config in config.agent.custom_tools:
    # 动态导入类
    module_name, class_name = tool_config["class"].rsplit(".", 1)
    module = importlib.import_module(module_name)
    tool_class = getattr(module, class_name)

    # 实例化并注册
    tool = tool_class(**tool_config.get("config", {}))
    self.tools.register(tool)
```

## 工具执行流程

**位置**: `nanobot/agent/tools/registry.py:46-55`

```python
async def execute(self, name: str, params: dict) -> str:
    """
    执行工具

    Args:
        name: 工具名称
        params: LLM 传递的参数

    Returns:
        工具执行结果

    Raises:
        ValueError: 工具不存在或参数错误
    """
    # 1. 查找工具
    tool = self._tools.get(name)
    if not tool:
        return f"Error: Unknown tool '{name}'"

    # 2. 验证参数
    errors = tool.validate_params(params)
    if errors:
        return f"Parameter errors:\n" + "\n".join(errors)

    # 3. 执行工具
    try:
        result = await tool.execute(**params)
        return result
    except Exception as e:
        logger.exception(f"Error executing {name}")
        return f"Error executing {name}: {str(e)}"
```

## 错误处理

### 1. 参数验证错误

```python
def validate_params(self, params: dict) -> list[str] | None:
    errors = []

    # 自定义验证
    if "file_path" in params:
        path = Path(params["file_path"])
        if not path.is_absolute():
            errors.append("file_path must be absolute")

    return errors if errors else None
```

### 2. 执行错误

```python
async def execute(self, **kwargs) -> str:
    try:
        # 工具逻辑
        result = await self._do_something()
        return result
    except FileNotFoundError:
        return "Error: File not found"
    except PermissionError:
        return "Error: Permission denied"
    except Exception as e:
        # 避免泄露敏感信息
        return f"Error: {type(e).__name__}"
```

### 3. 超时控制

```python
async def execute(self, **kwargs) -> str:
    try:
        result = await asyncio.wait_for(
            self._long_running_task(),
            timeout=30.0
        )
        return result
    except asyncio.TimeoutError:
        return "Error: Operation timed out"
```

## 最佳实践

### 1. 异步优先

使用 `async/await` 避免阻塞事件循环:

```python
# ✅ 好
async def execute(self, url: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.text

# ❌ 不好 (阻塞)
def execute(self, url: str) -> str:
    import requests
    response = requests.get(url)  # 阻塞调用
    return response.text
```

如果必须使用同步库:

```python
async def execute(self, **kwargs) -> str:
    # 在线程池中运行
    result = await asyncio.to_thread(
        self._sync_function,
        **kwargs
    )
    return result
```

### 2. 返回格式化结果

优先返回 Markdown 格式:

```python
# ✅ 好
return f"""## Search Results

Found 3 results:

1. **Item 1**
   - Price: $10
   - URL: https://...

2. **Item 2**
   - Price: $20
   - URL: https://...
"""

# ❌ 不好
return "Item 1: $10, https://...\nItem 2: $20, https://..."
```

### 3. 清晰的错误消息

```python
# ✅ 好
return "Error: API key is invalid. Please check your configuration."

# ❌ 不好
return "Error"
```

### 4. 控制输出长度

```python
async def execute(self, **kwargs) -> str:
    result = await self._fetch_data()

    # 截断过长输出
    if len(result) > 2000:
        result = result[:2000] + "\n... (truncated, total length: {len(result)})"

    return result
```

### 5. 安全性

```python
# 文件路径检查
def _validate_path(self, path: str) -> bool:
    path = Path(path).resolve()
    workspace = Path(self.workspace).resolve()

    # 确保在 workspace 内
    return path.is_relative_to(workspace)

# SQL 注入防护
def _validate_query(self, query: str) -> bool:
    # 仅允许 SELECT
    return query.strip().upper().startswith("SELECT")
```

## 测试工具

### 单元测试

```python
import pytest
from myproject.tools import WeatherTool

@pytest.mark.asyncio
async def test_weather_tool():
    tool = WeatherTool()

    # 测试参数验证
    errors = tool.validate_params({"location": "Beijing"})
    assert errors is None

    errors = tool.validate_params({})
    assert "location" in str(errors)

    # 测试执行 (mock API)
    with patch("myproject.tools.weather._fetch_weather") as mock:
        mock.return_value = {"temp": 25, "description": "Sunny"}
        result = await tool.execute(location="Beijing")
        assert "25°C" in result
        assert "Sunny" in result
```

### 集成测试

```python
@pytest.mark.asyncio
async def test_tool_in_agent_loop():
    # 创建 AgentLoop
    agent = AgentLoop(...)
    agent.tools.register(WeatherTool())

    # 模拟用户消息
    msg = InboundMessage(
        channel="test",
        sender_id="user1",
        chat_id="chat1",
        content="What's the weather in Beijing?"
    )

    # 处理消息
    response = await agent._process_message(msg)

    # 验证响应
    assert "Beijing" in response.content
```

## 下一步

- 查看内置工具实现: [文件系统工具](../../nanobot/agent/tools/filesystem.py)
- 了解工具注册机制: [ToolRegistry](../../nanobot/agent/tools/registry.py)
- 学习如何添加 Skills: [添加 Skills 指南](./adding-skills.md)

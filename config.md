# nanobot配置文件说明
## agents 配置
### defaults
关于`agents`的默认配置, 用在代码中的`AgentLoop`的初始化, 默认所有都是用default的配置

```json
"agents": {
    "defaults": {
      "workspace": "~/.nanobot/workspace",
      "model": "MiniMaxAI/MiniMax-M2.5",
      "maxTokens": 8192,
      "temperature": 0.1,
      "maxToolIterations": 40,
      "memoryWindow": 100
    }
  }
```

对应的pydantic定义的shcema
```python
class AgentDefaults(Base):
    """Default agent configuration."""

    workspace: str = "~/.nanobot/workspace"
    model: str = "anthropic/claude-opus-4-5"
    max_tokens: int = 8192
    temperature: float = 0.1
    max_tool_iterations: int = 40
    memory_window: int = 100


class AgentsConfig(Base):
    """Agent configuration."""

    defaults: AgentDefaults = Field(default_factory=AgentDefaults)
```

代码中用到的地方：
```python
agent_loop = AgentLoop(
    bus=bus,
    provider=provider,
    workspace=config.workspace_path,
    model=config.agents.defaults.model,
    temperature=config.agents.defaults.temperature,
    max_tokens=config.agents.defaults.max_tokens,
    max_iterations=config.agents.defaults.max_tool_iterations,
    memory_window=config.agents.defaults.memory_window,
    brave_api_key=config.tools.web.search.api_key or None,
    exec_config=config.tools.exec,
    cron_service=cron,
    restrict_to_workspace=config.tools.restrict_to_workspace,
    mcp_servers=config.tools.mcp_servers,
    channels_config=config.channels,
)

class AgentLoop:
    """
    The agent loop is the core processing engine.

    It:
    1. Receives messages from the bus
    2. Builds context with history, memory, skills
    3. Calls the LLM
    4. Executes tool calls
    5. Sends responses back
    """

    def __init__(
        self,
        bus: MessageBus,
        provider: LLMProvider,
        workspace: Path,
        model: str | None = None,
        max_iterations: int = 40,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        memory_window: int = 100,
        brave_api_key: str | None = None,
        exec_config: ExecToolConfig | None = None,
        cron_service: CronService | None = None,
        restrict_to_workspace: bool = False,
        session_manager: SessionManager | None = None,
        mcp_servers: dict | None = None,
        channels_config: ChannelsConfig | None = None,
    ):
        """Initialize the agent loop engine.

        Args:
            bus: Message bus for receiving inbound messages and publishing outbound responses
            provider: LLM provider instance (OpenAI, Anthropic, etc.) for model inference
            workspace: Root directory path for file operations and session storage
            model: Model identifier to use (defaults to provider's default model if None)
            max_iterations: Maximum number of LLM-tool iterations per message (prevents infinite loops)
            temperature: LLM sampling temperature (0.0-1.0), lower = more deterministic
            max_tokens: Maximum tokens to generate per LLM response
            memory_window: Number of recent history messages to include in context
            brave_api_key: API key for Brave web search tool (optional)
            exec_config: Configuration for shell command execution (timeout, restrictions)
            cron_service: Optional cron service instance for scheduled task management
            restrict_to_workspace: If True, file/exec tools can only access workspace directory
            session_manager: Custom session manager (creates default if None)
            mcp_servers: Dictionary of MCP server configurations for external tool integration
            channels_config: Channel-specific configuration (routing, permissions, etc.)
        """
        from nanobot.config.schema import ExecToolConfig
        self.bus = bus  # 消息总线，用于跨模块通信
        self.channels_config = channels_config  # 频道配置，定义各频道的路由和权限规则
        self.provider = provider  # LLM 提供者，负责调用底层语言模型
        self.workspace = workspace  # 工作空间根目录，所有文件操作的基准路径
        self.model = model or provider.get_default_model()  # 实际使用的模型名称
        self.max_iterations = max_iterations  # 单次对话的最大工具调用迭代次数
        self.temperature = temperature  # 控制生成文本的随机性
        self.max_tokens = max_tokens  # 限制单次生成的最大长度
        self.memory_window = memory_window  # 滑动窗口大小，控制上下文中保留多少历史消息
        self.brave_api_key = brave_api_key  # Brave 搜索 API 凭证
        self.exec_config = exec_config or ExecToolConfig()  # Shell 执行配置，包含超时等安全参数
        self.cron_service = cron_service  # 定时任务服务，支持周期性任务调度
        self.restrict_to_workspace = restrict_to_workspace  # 沙箱模式开关，限制文件和命令访问范围

        self.context = ContextBuilder(workspace)  # 上下文构建器，组装 LLM 提示词（系统消息、历史、当前输入）
        self.sessions = session_manager or SessionManager(workspace)  # 会话管理器，持久化每个频道/聊天的对话历史
        self.tools = ToolRegistry()  # 工具注册表，存储所有可用工具的定义和执行器
        self.subagents = SubagentManager(  # 子 Agent 管理器，支持并行处理独立任务
            provider=provider,
            workspace=workspace,
            bus=bus,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            brave_api_key=brave_api_key,
            exec_config=self.exec_config,
            restrict_to_workspace=restrict_to_workspace,
        )

        self._running = False  # 运行状态标志，控制主循环的生命周期
        self._mcp_servers = mcp_servers or {}  # MCP 服务器配置字典，存储外部工具集成信息
        self._mcp_stack: AsyncExitStack | None = None  # 异步上下文管理器，管理 MCP 连接的生命周期
        self._mcp_connected = False  # MCP 连接状态标志，表示是否已成功连接
        self._mcp_connecting = False  # MCP 连接中标志，防止重复连接
        self._consolidating: set[str] = set()  # 正在进行记忆整合的会话键集合
        self._consolidation_tasks: set[asyncio.Task] = set()  # 记忆整合任务的强引用集合，防止 GC 回收
        self._consolidation_locks: dict[str, asyncio.Lock] = {}  # 每个会话的整合锁，防止并发整合冲突
        self._register_default_tools()  # 注册默认工具集（文件、Shell、Web 等）
```

## tools 配置
### exec
```json
"tools": {
    "exec": {
      "timeout": 60
    }
  }
```

pydantic定义的schema:
```python
class ExecToolConfig(Base):
    """Shell exec tool configuration."""

    timeout: int = 60
```

也就是这个配置只有`timeout`这一个参数

### restrictToWorkspace
这个参数定义限制nanobot是否只有自己的workspace权限，默认是`false`

```json
"tools": {
    "restrictToWorkspace": false
}

```

代码调用时在 `AgentLoop`初始化时传入

**如何控制权限?**
在注册工具函数时，如果`restrict_to_workspace=True`则

```python
def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        allowed_dir = self.workspace if self.restrict_to_workspace else None
        for cls in (ReadFileTool, WriteFileTool, EditFileTool, ListDirTool):
            self.tools.register(cls(workspace=self.workspace, allowed_dir=allowed_dir))
```

### mcpServers
```json
"tools": {
    "mcpServers": {}
}
```

这个配置在`AgentLoop`初始化时传入，使用位置在:
```python
async def _connect_mcp(self) -> None:
    """Connect to configured MCP servers (one-time, lazy)."""
    if self._mcp_connected or self._mcp_connecting or not self._mcp_servers:
        return
```

如果没有配置`mcpServers`会直接返回


## channels 配置
### `sendProgress` & `sendToolHints`
这俩配置用于控制是否显示agent处理进度

```json
"channels": {
    "sendProgress": true,
    "sendToolHints": false
}
```

代码中使用位置，作为回调函数中的参数使用，其配置在`AgentLoop`初始化时传入
```python
response = await agent_loop.process_direct(message, session_id, on_progress=_cli_progress)

async def _cli_progress(content: str, *, tool_hint: bool = False) -> None:
    ch = agent_loop.channels_config
    if ch and tool_hint and not ch.send_tool_hints:
        return
    if ch and not tool_hint and not ch.send_progress:
        return
    console.print(f"  [dim]↳ {content}[/dim]")

```
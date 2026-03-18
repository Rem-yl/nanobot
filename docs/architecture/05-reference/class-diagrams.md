# 类图参考

本文档使用 Mermaid 类图展示 nanobot 的核心类结构和依赖关系。

## 核心类层次结构

### AgentLoop & 依赖组件

```mermaid
classDiagram
    class AgentLoop {
        -Config config
        -MessageBus bus
        -LLMProvider provider
        -ToolRegistry tools
        -ContextBuilder context
        -SessionManager sessions
        -SubagentManager subagents
        -MemoryStore memory
        -SkillsLoader skills
        -dict~str,Lock~ _consolidation_locks
        +run() void
        -_process_message(InboundMessage) OutboundMessage
        -_run_agent_loop(messages, max_iterations) str
        -_consolidate_memory(Session) void
        -_get_consolidation_lock(str) Lock
    }

    class MessageBus {
        +Queue~InboundMessage~ inbound
        +Queue~OutboundMessage~ outbound
        +publish_inbound(InboundMessage) void
        +publish_outbound(OutboundMessage) void
        +consume_inbound(timeout) InboundMessage
        +consume_outbound() OutboundMessage
    }

    class ContextBuilder {
        -Path workspace
        -MemoryStore memory
        -SkillsLoader skills
        +build_system_prompt(skill_names) str
        +build_messages(history, current, media, channel, chat_id) list
        -_get_identity() str
        -_load_bootstrap_files() str
        -_build_user_content(text, media) str|list
        -_inject_runtime_context(content, channel, chat_id) str
    }

    class SessionManager {
        -Path workspace
        -dict~str,Session~ _cache
        +get_or_create(key) Session
        +save(Session) void
        +list_sessions() list
        -_load(key) Session
        -_safe_key(key) str
    }

    class MemoryStore {
        -Path workspace
        +read_long_term() str
        +write_long_term(content) void
        +append_history(entry) void
        +get_memory_context() str
        +consolidate(Session, force_all, provider, config) void
        -_format_messages(messages) str
        -_get_save_memory_tool() dict
    }

    class SkillsLoader {
        -Path workspace
        -Path builtin_skills
        -dict~str,dict~ _skills
        +get_always_skills() list
        +load_skills_for_context(skill_names) str
        +build_skills_summary() str
        -_discover_skills() void
        -_parse_skill(path) dict
        -_check_requirements(skill_meta) tuple
    }

    class SubagentManager {
        -Config config
        -LLMProvider provider
        -MessageBus bus
        -ToolRegistry tools
        -SessionManager sessions
        -ContextBuilder context
        -dict~str,Task~ _running_tasks
        +spawn(task, label, origin_channel, origin_chat_id) str
        -_run_subagent(...) str
        -_announce_result(...) void
    }

    AgentLoop --> MessageBus
    AgentLoop --> ContextBuilder
    AgentLoop --> SessionManager
    AgentLoop --> MemoryStore
    AgentLoop --> SkillsLoader
    AgentLoop --> SubagentManager
    ContextBuilder --> MemoryStore
    ContextBuilder --> SkillsLoader
```

## Provider 系统

### LLMProvider 抽象层

```mermaid
classDiagram
    class LLMProvider {
        <<abstract>>
        +chat(messages, tools, model, temperature, max_tokens)* LLMResponse
    }

    class LLMResponse {
        +str content
        +list~ToolCallRequest~ tool_calls
        +str finish_reason
        +dict usage
        +str reasoning_content
        +bool has_tool_calls
    }

    class ToolCallRequest {
        +str id
        +str name
        +dict arguments
    }

    class LiteLLMProvider {
        -Config config
        -ProviderSpec spec
        +chat(messages, tools, model, temperature, max_tokens) LLMResponse
        -_resolve_model(model) str
        -_sanitize_messages(messages) list
        -_setup_env(api_key, api_base) void
        -_apply_cache_control(messages, tools, model) void
    }

    class CustomProvider {
        -Config config
        +chat(messages, tools, model, temperature, max_tokens) LLMResponse
    }

    class OpenAICodexProvider {
        -str access_token
        +chat(messages, tools, model, temperature, max_tokens) LLMResponse
        +login() void
    }

    LLMProvider <|-- LiteLLMProvider
    LLMProvider <|-- CustomProvider
    LLMProvider <|-- OpenAICodexProvider
    LiteLLMProvider ..> LLMResponse
    CustomProvider ..> LLMResponse
    LLMResponse *-- ToolCallRequest
```

### ProviderSpec 注册表

```mermaid
classDiagram
    class ProviderSpec {
        +str name
        +tuple keywords
        +str env_key
        +str litellm_prefix
        +bool is_gateway
        +bool is_oauth
        +str default_api_base
        +tuple model_overrides
        +tuple env_extras
        +str detect_by_key_prefix
        +str detect_by_base_keyword
        +bool strip_model_prefix
        +tuple skip_prefixes
    }

    class ProvidersConfig {
        +ProviderConfig anthropic
        +ProviderConfig openai
        +ProviderConfig deepseek
        +ProviderConfig gemini
        +ProviderConfig zhipu
        +ProviderConfig dashscope
        +ProviderConfig moonshot
        +ProviderConfig minimax
        +ProviderConfig groq
        +ProviderConfig openrouter
        +ProviderConfig aihubmix
        +ProviderConfig siliconflow
        +ProviderConfig volcengine
        +ProviderConfig vllm
        +ProviderConfig custom
        +ProviderConfig openai_codex
        +ProviderConfig github_copilot
    }

    class ProviderConfig {
        +str apiKey
        +str apiBase
    }

    ProvidersConfig *-- ProviderConfig
```

## Channel 系统

### BaseChannel 抽象层

```mermaid
classDiagram
    class BaseChannel {
        <<abstract>>
        +str name
        +MessageBus bus
        +Config config
        +start()* void
        +stop()* void
        +send(OutboundMessage)* void
        +is_allowed(sender_id) bool
    }

    class TelegramChannel {
        -str token
        -list allowFrom
        -Application _app
        +start() void
        +stop() void
        +send(OutboundMessage) void
        -_handle_message(Update) void
        -_download_media(media_obj) Path
    }

    class DiscordChannel {
        -str token
        -list allowFrom
        -WebSocket _ws
        -str _bot_user_id
        +start() void
        +stop() void
        +send(OutboundMessage) void
        -_gateway_loop() void
        -_handle_message(event) void
        -_send_heartbeat() void
    }

    class SlackChannel {
        -str botToken
        -str appToken
        -WebClient _web_client
        -SocketModeClient _socket_client
        +start() void
        +stop() void
        +send(OutboundMessage) void
        -_handle_message(event) void
        -_convert_markdown(text) str
    }

    class EmailChannel {
        -str imapHost
        -str smtpHost
        -int pollIntervalSeconds
        -set _processed_uids
        +start() void
        +stop() void
        +send(OutboundMessage) void
        -_poll_loop() void
        -_handle_message(msg) void
        -_send_smtp(to, subject, body) void
    }

    class FeishuChannel {
        -str appId
        -str appSecret
        -WSClient _ws_client
        -Thread _ws_thread
        +start() void
        +stop() void
        +send(OutboundMessage) void
        -_on_message_sync(data) void
        -_download_and_save_media(type, data) Path
        -_send_interactive_card(chat_id, content) void
    }

    BaseChannel <|-- TelegramChannel
    BaseChannel <|-- DiscordChannel
    BaseChannel <|-- SlackChannel
    BaseChannel <|-- EmailChannel
    BaseChannel <|-- FeishuChannel
```

### ChannelManager

```mermaid
classDiagram
    class ChannelManager {
        -Config config
        -MessageBus bus
        -dict~str,BaseChannel~ channels
        +start_all() void
        +stop_all() void
        -_dispatch_outbound() void
    }

    class InboundMessage {
        +str channel
        +str sender_id
        +str chat_id
        +str content
        +list media
        +datetime timestamp
        +str session_key_override
        +session_key() str
    }

    class OutboundMessage {
        +str channel
        +str chat_id
        +str content
        +list media
        +dict metadata
    }

    ChannelManager *-- BaseChannel
    ChannelManager ..> InboundMessage
    ChannelManager ..> OutboundMessage
    BaseChannel ..> InboundMessage
    BaseChannel ..> OutboundMessage
```

## 工具系统

### Tool 抽象层

```mermaid
classDiagram
    class Tool {
        <<abstract>>
        +str name*
        +str description*
        +get_definition()* dict
        +validate_params(params) list|None
        +execute(**kwargs)* str
    }

    class ReadFileTool {
        -Path workspace
        +name = "read_file"
        +description = "Read a file from disk"
        +get_definition() dict
        +execute(file_path) str
    }

    class WriteFileTool {
        -Path workspace
        +name = "write_file"
        +description = "Write content to a file"
        +get_definition() dict
        +execute(file_path, content) str
    }

    class EditFileTool {
        -Path workspace
        +name = "edit_file"
        +description = "Edit lines in a file"
        +get_definition() dict
        +execute(file_path, old_text, new_text) str
    }

    class ExecTool {
        -Path workspace
        -bool restrict_to_workspace
        +name = "exec"
        +description = "Execute shell command"
        +get_definition() dict
        +execute(command) str
    }

    class WebSearchTool {
        -str brave_api_key
        +name = "web_search"
        +description = "Search the web"
        +get_definition() dict
        +execute(query) str
    }

    class MessageTool {
        -MessageBus bus
        -bool _sent_in_turn
        +name = "message"
        +description = "Send a message"
        +get_definition() dict
        +execute(content, channel, chat_id, media) str
    }

    class SpawnTool {
        -SubagentManager subagents
        +name = "spawn"
        +description = "Create a subagent"
        +get_definition() dict
        +execute(task, label) str
    }

    class CronTool {
        -CronService cron
        +name = "cron"
        +description = "Manage scheduled tasks"
        +get_definition() dict
        +execute(action, **kwargs) str
    }

    class MCPTool {
        -MCPClient client
        -dict tool_def
        +name = "{mcp_tool_name}"
        +description = "{from tool_def}"
        +get_definition() dict
        +execute(**kwargs) str
    }

    Tool <|-- ReadFileTool
    Tool <|-- WriteFileTool
    Tool <|-- EditFileTool
    Tool <|-- ExecTool
    Tool <|-- WebSearchTool
    Tool <|-- MessageTool
    Tool <|-- SpawnTool
    Tool <|-- CronTool
    Tool <|-- MCPTool
```

### ToolRegistry

```mermaid
classDiagram
    class ToolRegistry {
        -dict~str,Tool~ _tools
        +register(tool) void
        +get_definitions() list
        +execute(name, params) str
    }

    ToolRegistry o-- Tool
```

## Session 系统

```mermaid
classDiagram
    class Session {
        +str key
        +list~dict~ messages
        +datetime created_at
        +datetime updated_at
        +dict metadata
        +int last_consolidated
        +get_history(max_messages) list
        +add_message(role, content, **kwargs) void
    }

    class SessionManager {
        -Path workspace
        -dict~str,Session~ _cache
        +get_or_create(key) Session
        +save(session) void
        +list_sessions() list
        -_load(key) Session
        -_safe_key(key) str
    }

    SessionManager o-- Session
```

## Cron 系统

```mermaid
classDiagram
    class CronJob {
        +str id
        +str name
        +CronPayload payload
        +CronSchedule schedule
        +CronState state
        +datetime created_at
        +datetime updated_at
    }

    class CronPayload {
        +str message
        +str channel
        +str to
    }

    class CronSchedule {
        +str at
        +int every_seconds
        +str cron_expr
        +str timezone
    }

    class CronState {
        +bool enabled
        +int next_run_at_ms
        +int last_run_at_ms
        +str last_status
        +str last_error
    }

    class CronService {
        -Path data_dir
        -AgentLoop agent
        -dict~str,CronJob~ _jobs
        -Task _timer_task
        +start() void
        +stop() void
        +add_job(name, message, schedule, payload) CronJob
        +remove_job(job_id) bool
        +list_jobs() list
        -_arm_timer() void
        -_on_timer() void
        -_execute_job(job) void
        -_compute_next_run(job) int
    }

    CronJob *-- CronPayload
    CronJob *-- CronSchedule
    CronJob *-- CronState
    CronService o-- CronJob
```

## 配置系统

```mermaid
classDiagram
    class Config {
        +AgentConfig agent
        +ProvidersConfig providers
        +ChannelsConfig channels
        +ToolsConfig tools
        +CronConfig cron
        +GatewayConfig gateway
        +WebSearchConfig web_search
        +dict mcp_servers
    }

    class AgentConfig {
        +str model
        +float temperature
        +int max_tokens
        +int max_iterations
        +int max_history
        +int memory_window
        +bool restrict_to_workspace
    }

    class ChannelsConfig {
        +TelegramConfig telegram
        +DiscordConfig discord
        +SlackConfig slack
        +EmailConfig email
        +FeishuConfig feishu
        +... other channels
    }

    class ToolsConfig {
        +bool restrict_to_workspace
        +dict mcp_servers
    }

    class CronConfig {
        +bool enabled
    }

    class GatewayConfig {
        +bool send_progress
        +bool send_tool_hints
        +HeartbeatConfig heartbeat
    }

    Config *-- AgentConfig
    Config *-- ProvidersConfig
    Config *-- ChannelsConfig
    Config *-- ToolsConfig
    Config *-- CronConfig
    Config *-- GatewayConfig
```

## 完整依赖关系图

```mermaid
graph TD
    Gateway[Gateway CLI] --> Config[Config]
    Gateway --> MessageBus[MessageBus]
    Gateway --> AgentLoop[AgentLoop]
    Gateway --> ChannelManager[ChannelManager]
    Gateway --> CronService[CronService]
    Gateway --> HeartbeatService[HeartbeatService]

    AgentLoop --> Config
    AgentLoop --> MessageBus
    AgentLoop --> LLMProvider[LLMProvider]
    AgentLoop --> ToolRegistry[ToolRegistry]
    AgentLoop --> ContextBuilder[ContextBuilder]
    AgentLoop --> SessionManager[SessionManager]
    AgentLoop --> SubagentManager[SubagentManager]

    ContextBuilder --> MemoryStore[MemoryStore]
    ContextBuilder --> SkillsLoader[SkillsLoader]

    SubagentManager --> LLMProvider
    SubagentManager --> ToolRegistry
    SubagentManager --> MessageBus
    SubagentManager --> SessionManager
    SubagentManager --> ContextBuilder

    ChannelManager --> MessageBus
    ChannelManager --> TelegramChannel[TelegramChannel]
    ChannelManager --> DiscordChannel[DiscordChannel]
    ChannelManager --> SlackChannel[SlackChannel]
    ChannelManager --> EmailChannel[EmailChannel]
    ChannelManager --> FeishuChannel[FeishuChannel]

    TelegramChannel --> MessageBus
    DiscordChannel --> MessageBus
    SlackChannel --> MessageBus
    EmailChannel --> MessageBus
    FeishuChannel --> MessageBus

    ToolRegistry --> Tool[Tool]
    Tool --> ReadFileTool[ReadFileTool]
    Tool --> WriteFileTool[WriteFileTool]
    Tool --> ExecTool[ExecTool]
    Tool --> WebSearchTool[WebSearchTool]
    Tool --> MessageTool[MessageTool]
    Tool --> SpawnTool[SpawnTool]
    Tool --> CronTool[CronTool]
    Tool --> MCPTool[MCPTool]

    MessageTool --> MessageBus
    SpawnTool --> SubagentManager
    CronTool --> CronService

    CronService --> AgentLoop
    HeartbeatService --> AgentLoop

    LLMProvider --> LiteLLMProvider[LiteLLMProvider]
    LLMProvider --> CustomProvider[CustomProvider]
    LLMProvider --> OpenAICodexProvider[OpenAICodexProvider]

    SessionManager --> Session[Session]

    CronService --> CronJob[CronJob]
```

## 类关系说明

### 继承关系 (Inheritance)

- **LLMProvider** ← LiteLLMProvider, CustomProvider, OpenAICodexProvider
- **BaseChannel** ← TelegramChannel, DiscordChannel, SlackChannel, EmailChannel, FeishuChannel
- **Tool** ← ReadFileTool, WriteFileTool, ExecTool, WebSearchTool, MessageTool, SpawnTool, CronTool, MCPTool

### 组合关系 (Composition)

- **AgentLoop** ◆ MessageBus, ContextBuilder, SessionManager, MemoryStore, SkillsLoader, SubagentManager
- **ContextBuilder** ◆ MemoryStore, SkillsLoader
- **ChannelManager** ◆ BaseChannel (多个)
- **ToolRegistry** ◆ Tool (多个)
- **CronJob** ◆ CronPayload, CronSchedule, CronState

### 聚合关系 (Aggregation)

- **SessionManager** ○ Session (多个)
- **CronService** ○ CronJob (多个)

### 依赖关系 (Dependency)

- **AgentLoop** → LLMProvider, ToolRegistry
- **SubagentManager** → LLMProvider, ToolRegistry, MessageBus
- **Channels** → MessageBus
- **Tools** → MessageBus, SubagentManager, CronService

## 使用这些类图

所有类图使用 Mermaid 语法,可以在以下环境中渲染:

1. **GitHub**: 自动渲染
2. **VS Code**: 安装 Mermaid Preview 插件
3. **在线工具**: https://mermaid.live
4. **文档生成**: MkDocs + mermaid2 插件

## 下一步

- 查看 [数据流图](./data-flow-diagrams.md) 了解运行时流程
- 阅读 [文件索引](./file-index.md) 定位具体代码
- 参考 [架构概览](../00-overview.md) 理解设计理念

# 数据流可视化图表

本文档使用 Mermaid 图表可视化 nanobot 的数据流动。

## 完整消息流转路径

```mermaid
graph TD
    A[用户发送消息] --> B[Channel._handle_message]
    B --> C{权限检查}
    C -->|允许| D[下载媒体文件]
    C -->|拒绝| Z[丢弃消息]
    D --> E[转录语音<br/>Groq Whisper]
    E --> F[创建 InboundMessage]
    F --> G[MessageBus.publish_inbound]
    G --> H[AgentLoop.run 轮询<br/>1秒超时]
    H --> I{斜杠命令?}
    I -->|/new| J[触发记忆整理<br/>清空会话]
    I -->|/help| K[返回帮助信息]
    I -->|普通消息| L[获取会话 Session]
    L --> M{需要整理?<br/>messages >= 100}
    M -->|是| N[后台异步整理<br/>不阻塞]
    M -->|否| O[构建上下文]
    N --> O
    O --> P[LLM + 工具循环<br/>max 40 iterations]
    P --> Q{有工具调用?}
    Q -->|是| R[执行工具]
    R --> S[添加工具结果]
    S --> P
    Q -->|否| T[保存会话<br/>JSONL]
    T --> U{message tool 发送?}
    U -->|是| V[跳过响应]
    U -->|否| W[创建 OutboundMessage]
    W --> X[MessageBus.publish_outbound]
    X --> Y[ChannelManager 路由]
    Y --> AA[Channel.send]
    AA --> AB[用户收到回复]
    J --> AB
    K --> AB
    V --> AB
```

## AgentLoop 核心流程

```mermaid
flowchart TD
    Start[AgentLoop.run 启动] --> Poll[轮询 inbound 队列<br/>timeout=1s]
    Poll --> Check{有消息?}
    Check -->|否| Poll
    Check -->|是| Cmd{斜杠命令?}

    Cmd -->|/new| New[整理记忆 + 清空会话]
    Cmd -->|/help| Help[返回帮助]
    Cmd -->|否| Session[获取/创建 Session]

    Session --> History[提取历史<br/>max_messages=100]
    History --> MemCheck{需要整理?}
    MemCheck -->|是| BgConsolidate[后台 consolidate]
    MemCheck -->|否| Context[构建上下文]
    BgConsolidate --> Context

    Context --> LLMLoop[LLM + 工具循环]
    LLMLoop --> Save[保存会话]
    Save --> MsgCheck{message tool?}
    MsgCheck -->|已发送| End[结束]
    MsgCheck -->|否| Send[发送响应]

    New --> End
    Help --> End
    Send --> End
```

## LLM 工具执行循环

```mermaid
flowchart TD
    Start[开始循环<br/>iteration=0] --> Check{iteration < 40?}
    Check -->|否| MaxIter[返回超时提示]
    Check -->|是| CallLLM[调用 LLM<br/>provider.chat]

    CallLLM --> HasTools{有工具调用?}
    HasTools -->|否| Return[返回 final_content]

    HasTools -->|是| Progress[发送进度消息]
    Progress --> Hint[发送工具提示]
    Hint --> AddAssist[添加 assistant 消息]

    AddAssist --> ToolLoop{遍历 tool_calls}
    ToolLoop --> Execute[执行工具<br/>tools.execute]
    Execute --> Truncate[截断结果<br/>> 500 chars]
    Truncate --> AddTool[添加 tool 消息]
    AddTool --> ToolLoop

    ToolLoop --> Inc[iteration += 1]
    Inc --> Check
```

## Provider 路由逻辑

```mermaid
flowchart TD
    Start[模型名: model] --> Prefix{显式前缀?}
    Prefix -->|是| Match1[匹配 provider<br/>deepseek/xxx → DeepSeek]
    Prefix -->|否| Keyword{关键词匹配?}

    Match1 --> HasKey1{有 api_key?}
    HasKey1 -->|是| Use1[使用该 provider]
    HasKey1 -->|否| Keyword

    Keyword -->|gpt-4| Match2[OpenAI]
    Keyword -->|claude| Match2[Anthropic]
    Keyword -->|deepseek| Match2[DeepSeek]
    Keyword -->|否| Fallback{回退策略}

    Match2 --> HasKey2{有 api_key?}
    HasKey2 -->|是| Use2[使用该 provider]
    HasKey2 -->|否| Fallback

    Fallback --> Gateway{有网关 provider?}
    Gateway -->|是| UseGateway[使用网关<br/>OpenRouter/AiHubMix]
    Gateway -->|否| First[第一个有 api_key<br/>的 provider]

    Use1 --> Resolve[解析模型名<br/>_resolve_model]
    Use2 --> Resolve
    UseGateway --> Resolve
    First --> Resolve

    Resolve --> SetupEnv[设置环境变量<br/>_setup_env]
    SetupEnv --> Call[调用 LiteLLM<br/>acompletion]
```

## Memory Consolidation 流程

```mermaid
sequenceDiagram
    participant Agent as AgentLoop
    participant Session as Session
    participant Memory as MemoryStore
    participant LLM as LLMProvider
    participant Files as Filesystem

    Agent->>Session: 检查未整理消息数
    Session-->>Agent: unconsolidated >= 100

    Agent->>Agent: 获取整理锁
    Agent->>Memory: consolidate(session)

    Memory->>Session: 提取旧消息
    Session-->>Memory: messages[last:keep]

    Memory->>Memory: 格式化为时间戳日志
    Memory->>Files: 读取 MEMORY.md
    Files-->>Memory: 当前长期记忆

    Memory->>LLM: chat(messages, save_memory tool)
    LLM-->>Memory: {history_entry, memory_update}

    Memory->>Files: 追加 HISTORY.md
    Memory->>Files: 覆盖 MEMORY.md

    Memory->>Session: 更新 last_consolidated
    Memory-->>Agent: 整理完成

    Agent->>Agent: 释放锁
```

## Subagent 执行流程

```mermaid
sequenceDiagram
    participant User as 用户
    participant Main as 主 Agent
    participant Spawn as SpawnTool
    participant Sub as Subagent
    participant Bus as MessageBus

    User->>Main: 请求任务
    Main->>Main: LLM 决策使用 spawn tool
    Main->>Spawn: execute(task, label)

    Spawn->>Spawn: 创建 task_id
    Spawn->>Sub: asyncio.create_task<br/>_run_subagent
    Spawn-->>Main: "Subagent started (id: xxx)"
    Main-->>User: 告知已创建子任务

    Note over Sub: 后台执行 (不阻塞)
    Sub->>Sub: 独立 LLM 循环<br/>max_iterations=15
    Sub->>Sub: 有限工具集<br/>无 message/spawn/cron

    Sub->>Sub: 完成任务
    Sub->>Bus: publish_inbound<br/>channel="system"
    Bus->>Main: consume_inbound

    Main->>Main: 检测系统消息
    Main->>Main: 加载原会话历史
    Main->>Main: LLM 总结结果
    Main-->>User: 报告子任务完成
```

## Cron 调度流程

```mermaid
flowchart TD
    Start[CronService.start] --> Load[加载 jobs.json]
    Load --> Arm[_arm_timer<br/>计算下次唤醒时间]

    Arm --> Sleep[asyncio.sleep<br/>until next_run_at_ms]
    Sleep --> Wake[_on_timer 唤醒]

    Wake --> Find[查找所有到期任务]
    Find --> Loop{遍历 due jobs}

    Loop --> Exec[_execute_job]
    Exec --> Direct[agent.process_direct<br/>session=cron:job_id]
    Direct --> Update[更新 job.state<br/>last_run, status]
    Update --> Next{计算 next_run}

    Next -->|at 模式| Disable[禁用/删除任务]
    Next -->|every 模式| CalcEvery[now + every_seconds]
    Next -->|cron 模式| CalcCron[下一个 cron 时间点]

    Disable --> Loop
    CalcEvery --> Loop
    CalcCron --> Loop

    Loop --> Save[保存 jobs.json]
    Save --> Arm
```

## Channel 消息处理 (以 Telegram 为例)

```mermaid
sequenceDiagram
    participant TG as Telegram Server
    participant Ch as TelegramChannel
    participant Bus as MessageBus
    participant Media as MediaDir
    participant Whisper as Groq Whisper

    TG->>Ch: Long Polling<br/>getUpdates
    Ch->>Ch: _handle_message

    alt 权限检查
        Ch->>Ch: is_allowed(sender_id)
        Ch-->>Ch: 拒绝则返回
    end

    alt 下载媒体
        Ch->>TG: bot.get_file(file_id)
        TG-->>Ch: file object
        Ch->>Media: download_to_drive
    end

    alt 语音转录
        Ch->>Whisper: transcribe(audio_file)
        Whisper-->>Ch: transcription text
    end

    Ch->>Ch: 创建 InboundMessage
    Ch->>Bus: publish_inbound(msg)
    Bus-->>Ch: 消息已入队
```

## Session 持久化

```mermaid
flowchart TD
    Start[session.messages.extend] --> Update[session.updated_at = now]
    Update --> Save[sessions.save<br/>session]

    Save --> Cache[更新内存缓存<br/>_cache[key] = session]
    Cache --> Path[生成文件路径<br/>{safe_key}.jsonl]

    Path --> Open[打开文件<br/>覆盖写入]
    Open --> Meta[写入 metadata 行<br/>_type=metadata]
    Meta --> Loop{遍历 messages}

    Loop --> WriteMsg[写入消息行<br/>JSON + \n]
    WriteMsg --> Loop

    Loop --> Close[关闭文件]
    Close --> End[保存完成]
```

## Context 构建流程

```mermaid
flowchart LR
    Start[开始构建] --> System[System Prompt]

    System --> Identity[1. Identity<br/>OS/Python/Workspace]
    Identity --> Bootstrap[2. Bootstrap Files<br/>AGENTS/SOUL/USER...]
    Bootstrap --> Memory[3. MEMORY.md<br/>长期事实]
    Memory --> AlwaysSkills[4. Always Skills<br/>完整内容]
    AlwaysSkills --> SkillsXML[5. Skills Summary<br/>XML 索引]

    SkillsXML --> History[6. Conversation History<br/>最近 100 条]
    History --> Current[7. Current Message<br/>文本 + base64 图片]

    Current --> Runtime[8. Runtime Context<br/>时间/Channel/ChatID]
    Runtime --> Messages[完整 messages 列表]
```

## 工具执行流程

```mermaid
sequenceDiagram
    participant LLM as LLM Response
    participant Loop as AgentLoop
    participant Registry as ToolRegistry
    participant Tool as Specific Tool

    LLM->>Loop: tool_calls: [{name, args}]
    Loop->>Registry: execute(name, args)

    Registry->>Registry: 查找 tool<br/>_tools.get(name)
    Registry->>Tool: validate_params(args)<br/>JSON Schema
    Tool-->>Registry: errors or None

    alt 参数错误
        Registry-->>Loop: "Parameter errors: ..."
    else 参数正确
        Registry->>Tool: execute(**args)
        Tool->>Tool: 执行工具逻辑
        Tool-->>Registry: result
        Registry-->>Loop: result
    end

    Loop->>Loop: 截断结果 (> 500 chars)
    Loop->>Loop: 添加 tool 消息到 history
```

## 组件依赖关系图

```mermaid
graph TD
    Gateway[Gateway CLI] --> Bus[MessageBus]
    Gateway --> Agent[AgentLoop]
    Gateway --> Channels[ChannelManager]
    Gateway --> Cron[CronService]
    Gateway --> Heartbeat[HeartbeatService]

    Agent --> Provider[LLMProvider]
    Agent --> Tools[ToolRegistry]
    Agent --> Context[ContextBuilder]
    Agent --> Sessions[SessionManager]
    Agent --> Subagents[SubagentManager]

    Context --> Memory[MemoryStore]
    Context --> Skills[SkillsLoader]

    Channels --> TG[TelegramChannel]
    Channels --> DC[DiscordChannel]
    Channels --> SL[SlackChannel]
    Channels --> EM[EmailChannel]
    Channels --> FS[FeishuChannel]

    Tools --> FS_Tools[FilesystemTools]
    Tools --> Shell[ExecTool]
    Tools --> Web[WebTools]
    Tools --> Msg[MessageTool]
    Tools --> Spawn[SpawnTool]
    Tools --> CT[CronTool]
    Tools --> MCP[MCPTools]

    Provider --> LiteLLM[LiteLLMProvider]
    Provider --> Custom[CustomProvider]

    Subagents --> Provider
    Subagents --> Tools
    Cron --> Agent
    Heartbeat --> Agent
```

## Skills 加载策略

```mermaid
flowchart TD
    Start[Skills 发现] --> Scan1[扫描 workspace/skills]
    Scan1 --> Scan2[扫描 nanobot/skills]

    Scan2 --> Parse[解析 frontmatter<br/>metadata]
    Parse --> Check{检查依赖}

    Check --> Bins{bins 存在?}
    Bins -->|否| Unavailable[标记 unavailable]
    Bins -->|是| Env{env 存在?}
    Env -->|否| Unavailable
    Env -->|是| Available[标记 available]

    Available --> Always{always=true?}
    Always -->|是| Level1[Level 1:<br/>完整注入 system prompt]
    Always -->|否| Level2[Level 2:<br/>XML 摘要列出]

    Level1 --> Inject[注入到上下文]
    Level2 --> XML[生成 XML 索引]
    Unavailable --> XML

    XML --> Agent[Agent 按需读取<br/>Level 3: Lazy Load]
```

## Heartbeat 两阶段模型

```mermaid
sequenceDiagram
    participant Timer as Timer Loop
    participant Service as HeartbeatService
    participant LLM as LLMProvider
    participant Agent as AgentLoop
    participant User as User

    Timer->>Service: 每 30 分钟唤醒
    Service->>Service: 读取 HEARTBEAT.md

    Note over Service,LLM: 阶段 1: 决策
    Service->>LLM: chat(HEARTBEAT.md, heartbeat tool)
    LLM-->>Service: {action: "skip"|"run", tasks}

    alt action = "skip"
        Service->>Timer: 继续休眠
    else action = "run"
        Note over Service,Agent: 阶段 2: 执行
        Service->>Agent: process_direct(tasks, session="heartbeat")
        Agent-->>Service: response
        Service->>User: 通知 (via MessageBus)
    end
```

## 使用这些图表

所有图表使用 Mermaid 语法,可以在以下环境中渲染:

1. **GitHub**: 自动渲染
2. **VS Code**: 安装 Mermaid Preview 插件
3. **在线工具**: https://mermaid.live
4. **文档生成**: MkDocs + mermaid2 插件

## 下一步

- 查看 [文件索引](./file-index.md) 定位具体代码
- 阅读 [类图参考](./class-diagrams.md) 了解类结构
- 参考 [扩展开发指南](../04-extension-guide/) 开发新功能

# Nanobot 配置文档

## 目录

- [一、配置文件概述](#一配置文件概述)
  - [1.1 配置文件位置与格式](#11-配置文件位置与格式)
  - [1.2 配置加载优先级](#12-配置加载优先级)
  - [1.3 最小可用配置](#13-最小可用配置)
  - [1.4 配置快速检查表](#14-配置快速检查表)
- [二、代理配置 (Agents)](#二代理配置-agents)
  - [2.1 字段速览](#21-字段速览)
  - [2.2 字段详解](#22-字段详解)
  - [2.3 完整配置示例](#23-完整配置示例)
  - [2.4 常见场景配置](#24-常见场景配置)
- [三、提供商配置 (Providers)](#三提供商配置-providers)
  - [3.1 提供商选择指南](#31-提供商选择指南)
  - [3.2 通用字段说明](#32-通用字段说明)
  - [3.3 提供商分类详解](#33-提供商分类详解)
  - [3.4 故障排查](#34-故障排查)
- [四、聊天渠道配置 (Channels)](#四聊天渠道配置-channels)
  - [4.1 全局配置](#41-全局配置)
  - [4.2 渠道分类表](#42-渠道分类表)
  - [4.3 各渠道详细配置](#43-各渠道详细配置)
  - [4.4 权限控制说明](#44-权限控制说明)
- [五、工具配置 (Tools)](#五工具配置-tools)
  - [5.1 Web 搜索工具](#51-web-搜索工具)
  - [5.2 Shell 执行工具](#52-shell-执行工具)
  - [5.3 工作空间沙箱](#53-工作空间沙箱)
  - [5.4 MCP 外部工具](#54-mcp-外部工具)
- [六、网关配置 (Gateway)](#六网关配置-gateway)
  - [6.1 服务器绑定](#61-服务器绑定)
  - [6.2 心跳服务](#62-心跳服务)
- [七、附录](#七附录)
  - [附录 A: 配置模板库](#附录-a-配置模板库)
  - [附录 B: 环境变量映射表](#附录-b-环境变量映射表)
  - [附录 C: 安全最佳实践](#附录-c-安全最佳实践)
  - [附录 D: 字段速查索引](#附录-d-字段速查索引)

---

## 一、配置文件概述

### 1.1 配置文件位置与格式

**配置文件路径**: `~/.nanobot/config.json`

Nanobot 使用 JSON 格式的配置文件，文件编码为 UTF-8。配置文件会在首次运行时自动创建默认配置。

**配置加载逻辑**:
- 配置文件位置由 `nanobot/config/loader.py:get_config_path()` 定义
- 如果配置文件不存在，会使用所有字段的默认值
- 配置文件格式错误时会显示警告并回退到默认配置

### 1.2 配置加载优先级

Nanobot 支持三种配置方式，优先级从高到低：

1. **环境变量** (最高优先级)
   - 格式: `NANOBOT_` + 大写路径 + `__` 分隔符
   - 示例: `NANOBOT_AGENTS__DEFAULTS__MODEL="deepseek/deepseek-chat"`
   - 详见 [附录 B: 环境变量映射表](#附录-b-环境变量映射表)

2. **配置文件** (`~/.nanobot/config.json`)
   - JSON 格式，支持 camelCase 和 snake_case 两种字段命名
   - 示例: `"maxTokens"` 和 `"max_tokens"` 等价

3. **默认值** (最低优先级)
   - 所有字段都有合理的默认值，确保零配置可启动

### 1.3 最小可用配置

最简单的配置只需要一个 API Key，即可启动 nanobot：

```json
{
  "providers": {
    "anthropic": {
      "apiKey": "sk-ant-api03-YOUR_API_KEY_HERE"
    }
  }
}
```

或者使用环境变量:

```bash
export NANOBOT_PROVIDERS__ANTHROPIC__API_KEY="sk-ant-api03-YOUR_API_KEY_HERE"
uv run nanobot chat
```

**说明**:
- 默认使用 `claude-opus-4-5` 模型
- 默认工作空间为 `~/.nanobot/workspace`
- 所有聊天渠道默认关闭（`enabled: false`）
- CLI 交互模式无需配置渠道

### 1.4 配置快速检查表

在启动 nanobot 之前，可根据使用场景检查以下配置：

| 使用场景 | 必需配置 | 可选配置 |
|---------|---------|---------|
| **CLI 交互** | `providers.*.apiKey` | `agents.defaults.model`, `agents.defaults.workspace` |
| **Telegram Bot** | `providers.*.apiKey`<br>`channels.telegram.token`<br>`channels.telegram.enabled: true` | `channels.telegram.allowFrom` (白名单)<br>`channels.telegram.proxy` (代理) |
| **Slack Bot** | `providers.*.apiKey`<br>`channels.slack.botToken`<br>`channels.slack.appToken`<br>`channels.slack.enabled: true` | `channels.slack.groupPolicy`<br>`channels.slack.dm.allowFrom` |
| **Email 助手** | `providers.*.apiKey`<br>`channels.email.enabled: true`<br>`channels.email.consentGranted: true`<br>IMAP/SMTP 完整配置 | `channels.email.allowFrom`<br>`channels.email.pollIntervalSeconds` |
| **企业内网部署** | `providers.*.apiKey`<br>`tools.restrictToWorkspace: true` | `gateway.host`, `gateway.port`<br>`channels.*.allowFrom` (严格白名单) |
| **本地模型** | `providers.vllm.apiBase`<br>`agents.defaults.model` | `providers.vllm.apiKey` (可选)<br>`agents.defaults.maxTokens` |
| **Web 搜索** | `tools.web.search.apiKey` (Brave) | `tools.web.search.maxResults` |
| **MCP 工具集成** | `tools.mcpServers.*` | `tools.mcpServers.*.toolTimeout` |

---

## 二、代理配置 (Agents)

代理（Agent）是 nanobot 的核心处理引擎，负责接收消息、调用 LLM、执行工具、返回响应。

### 2.1 字段速览

| 字段名 | 类型 | 默认值 | 用途 |
|-------|------|--------|------|
| `workspace` | `string` | `~/.nanobot/workspace` | 工作目录路径 |
| `model` | `string` | `anthropic/claude-opus-4-5` | LLM 模型选择 |
| `maxTokens` | `int` | `8192` | 生成长度限制 |
| `temperature` | `float` | `0.1` | 采样温度 (0.0-1.0) |
| `maxToolIterations` | `int` | `40` | 单次对话最大工具调用次数 |
| `memoryWindow` | `int` | `100` | 上下文窗口大小（保留历史消息数） |

### 2.2 字段详解

#### `workspace`

**类型**: `string`
**默认值**: `~/.nanobot/workspace`
**用途**: 工作目录路径，所有文件操作的基准路径

**详细说明**:
- **功能描述**: 定义 Agent 的工作根目录，所有文件读写、会话存储都在此目录下进行
- **使用场景**:
  - 需要隔离不同项目的工作文件时
  - 多用户环境下为每个用户分配独立工作空间
  - 集成到 CI/CD 流程中指定临时工作目录
- **配置要求**:
  - 支持 `~` 和 `$HOME` 环境变量展开
  - 路径会自动创建（如果不存在）
  - 需要对该目录有读写权限

**配置示例**:
```json
{
  "agents": {
    "defaults": {
      "workspace": "~/projects/my-bot-workspace"
    }
  }
}
```

**注意事项**:
- 🔗 **相关配置**: [`tools.restrictToWorkspace`](#restricttoworkspace) - 启用沙箱模式时，所有工具只能访问此目录
- 📊 **推荐值**: 为生产环境使用专用目录，避免与个人文件混淆

**代码使用位置**:
- `nanobot/config/schema.py:295` - `workspace_path` 属性展开路径
- `nanobot/cli/commands.py:280` - Gateway 初始化时传递给 AgentLoop
- `nanobot/agent/loop.py:110` - AgentLoop 构造函数接收并存储

---

#### `model`

**类型**: `string`
**默认值**: `anthropic/claude-opus-4-5`
**用途**: 指定使用的 LLM 模型名称

**详细说明**:
- **功能描述**: 控制 Agent 使用哪个 LLM 模型进行推理，支持显式前缀（`provider/model`）和关键词匹配
- **使用场景**:
  - 切换不同能力的模型（如 Claude Opus vs Sonnet）
  - 测试新模型的性能和成本
  - 针对特定任务选择专用模型（如代码生成、创意写作）
- **配置要求**:
  - 格式: `provider/model-name` 或直接 `model-name`
  - 必须与 `providers` 配置中的某个提供商匹配
  - 详见 [3.1 提供商选择指南](#31-提供商选择指南) 了解匹配逻辑

**配置示例**:
```json
{
  "agents": {
    "defaults": {
      "model": "deepseek/deepseek-chat"
    }
  },
  "providers": {
    "deepseek": {
      "apiKey": "sk-xxx"
    }
  }
}
```

**注意事项**:
- 🔗 **相关配置**: [`providers`](#三提供商配置-providers) - 必须配置对应提供商的 API Key
- ⚠️ **常见错误**:
  - 模型名称拼写错误导致无法匹配提供商
  - 配置了模型但未提供对应的 API Key
- 📊 **推荐值**:
  - 日常使用: `deepseek/deepseek-chat` (高性价比)
  - 复杂任务: `anthropic/claude-opus-4-5` (最强能力)
  - 快速响应: `anthropic/claude-sonnet-4-5` (平衡速度与能力)

**代码使用位置**:
- `nanobot/config/schema.py:303` - `_match_provider()` 使用此字段匹配提供商
- `nanobot/cli/commands.py:280` - 传递给 AgentLoop
- `nanobot/agent/loop.py:111` - 存储并在每次 LLM 调用时使用

---

#### `maxTokens`

**类型**: `int`
**默认值**: `8192`
**用途**: 限制 LLM 单次生成的最大 token 数量

**详细说明**:
- **功能描述**: 控制 LLM 每次响应可以生成的最大长度，防止无限生成和成本失控
- **使用场景**:
  - 需要简洁回答时降低此值（如 `1024`）
  - 需要长篇内容时提高此值（如 `16384`）
  - 成本敏感场景下限制输出长度
- **配置要求**:
  - 不能超过模型的最大上下文长度
  - 需考虑输入 tokens + 输出 tokens 总和不超过模型限制
  - 不同模型有不同的限制（Claude Opus 4.5 最大 200K tokens）

**配置示例**:
```json
{
  "agents": {
    "defaults": {
      "maxTokens": 4096
    }
  }
}
```

**注意事项**:
- 📊 **推荐值**:
  - 简短对话: `2048 - 4096`
  - 代码生成: `8192`
  - 长文档生成: `16384 - 32768`
- ⚠️ **常见错误**: 设置过小导致回答被截断

**代码使用位置**:
- `nanobot/cli/commands.py:280` - 传递给 AgentLoop
- `nanobot/agent/loop.py:114` - 存储并在 LLM 调用时作为参数

---

#### `temperature`

**类型**: `float`
**默认值**: `0.1`
**用途**: 控制生成文本的随机性（0.0 = 确定性，1.0 = 高随机性）

**详细说明**:
- **功能描述**: 调整 LLM 采样的随机程度，影响输出的创意性和一致性
- **使用场景**:
  - 代码生成、技术文档：使用低温度（`0.1 - 0.3`）确保准确性
  - 创意写作、头脑风暴：使用高温度（`0.7 - 1.0`）增加多样性
  - 客服问答：使用中等温度（`0.3 - 0.5`）平衡准确性和自然度
- **配置要求**:
  - 范围: `0.0 - 1.0`
  - 某些模型有特殊限制（如 Moonshot Kimi K2.5 要求 >= 1.0）

**配置示例**:
```json
{
  "agents": {
    "defaults": {
      "temperature": 0.7
    }
  }
}
```

**注意事项**:
- 📊 **推荐值**:
  - 代码助手: `0.1`
  - 文档写作: `0.3`
  - 创意写作: `0.8`
- ⚠️ **特殊情况**: Moonshot Kimi K2.5 强制 `temperature >= 1.0`（由 `providers/registry.py` 自动处理）

**代码使用位置**:
- `nanobot/cli/commands.py:280` - 传递给 AgentLoop
- `nanobot/agent/loop.py:113` - 存储并在 LLM 调用时使用
- `nanobot/providers/registry.py:335` - 某些模型会覆盖此值

---

#### `maxToolIterations`

**类型**: `int`
**默认值**: `40`
**用途**: 限制单次对话中 Agent 可以调用工具的最大次数

**详细说明**:
- **功能描述**: 防止 Agent 陷入无限工具调用循环，同时允许复杂任务完成多步骤操作
- **使用场景**:
  - 复杂任务（如多文件重构）：提高限制（`50 - 100`）
  - 简单问答：降低限制（`10 - 20`）节省成本
  - 防止死循环：保持合理上限
- **配置要求**:
  - 必须 > 0
  - 每次工具调用都会消耗 1 次迭代计数
  - 达到上限后 Agent 会强制结束并返回当前状态

**配置示例**:
```json
{
  "agents": {
    "defaults": {
      "maxToolIterations": 60
    }
  }
}
```

**注意事项**:
- 📊 **推荐值**:
  - 普通对话: `20 - 40`
  - 代码项目: `50 - 80`
  - 复杂分析: `80 - 100`
- ⚠️ **成本影响**: 每次迭代都会调用 LLM，迭代次数越多成本越高

**代码使用位置**:
- `nanobot/cli/commands.py:280` - 传递给 AgentLoop
- `nanobot/agent/loop.py:112` - 存储为 `max_iterations`
- `nanobot/agent/loop.py` - 在主循环中检查迭代计数

---

#### `memoryWindow`

**类型**: `int`
**默认值**: `100`
**用途**: 上下文窗口大小，控制保留多少条历史消息

**详细说明**:
- **功能描述**: 定义滑动窗口的大小，决定 Agent 可以"记住"多少轮对话历史
- **使用场景**:
  - 短期对话：降低窗口（`20 - 50`）节省 tokens
  - 长期项目：提高窗口（`100 - 200`）保持上下文连贯性
  - 技术支持会话：中等窗口（`50 - 80`）
- **配置要求**:
  - 窗口越大，每次调用 LLM 消耗的 input tokens 越多
  - 需要平衡上下文完整性和成本
  - 历史消息超过窗口大小时，旧消息会被移除

**配置示例**:
```json
{
  "agents": {
    "defaults": {
      "memoryWindow": 150
    }
  }
}
```

**注意事项**:
- 📊 **推荐值**:
  - 快速问答: `20 - 40`
  - 日常助手: `60 - 100`
  - 长期项目: `100 - 200`
- ⚠️ **成本影响**: 窗口越大，每次请求的输入 tokens 越多

**代码使用位置**:
- `nanobot/cli/commands.py:280` - 传递给 AgentLoop
- `nanobot/agent/loop.py:115` - 存储并在构建上下文时使用
- `nanobot/agent/context.py` - 使用此值截取历史消息

---

### 2.3 完整配置示例

```json
{
  "agents": {
    "defaults": {
      "workspace": "~/.nanobot/workspace",
      "model": "deepseek/deepseek-chat",
      "maxTokens": 8192,
      "temperature": 0.1,
      "maxToolIterations": 40,
      "memoryWindow": 100
    }
  }
}
```

### 2.4 常见场景配置

#### 场景 1: 代码助手（高精度，低成本）

```json
{
  "agents": {
    "defaults": {
      "workspace": "~/code-projects",
      "model": "deepseek/deepseek-chat",
      "maxTokens": 8192,
      "temperature": 0.1,
      "maxToolIterations": 60,
      "memoryWindow": 80
    }
  }
}
```

#### 场景 2: 创意写作（高随机性）

```json
{
  "agents": {
    "defaults": {
      "workspace": "~/creative-writing",
      "model": "anthropic/claude-opus-4-5",
      "maxTokens": 16384,
      "temperature": 0.8,
      "maxToolIterations": 20,
      "memoryWindow": 50
    }
  }
}
```

#### 场景 3: 企业内网（严格沙箱）

```json
{
  "agents": {
    "defaults": {
      "workspace": "/opt/nanobot/workspace",
      "model": "openrouter/anthropic/claude-sonnet-4-5",
      "maxTokens": 8192,
      "temperature": 0.2,
      "maxToolIterations": 40,
      "memoryWindow": 100
    }
  },
  "tools": {
    "restrictToWorkspace": true
  }
}
```

---

## 三、提供商配置 (Providers)

提供商（Provider）定义了 nanobot 如何连接到各种 LLM 服务。

### 3.1 提供商选择指南

Nanobot 使用智能匹配逻辑自动选择提供商，匹配规则按以下优先级执行：

#### 匹配优先级（从高到低）

1. **显式前缀匹配**
   模型名称包含 `provider/` 前缀时，直接匹配该提供商
   ```json
   "model": "deepseek/deepseek-chat"  → providers.deepseek
   "model": "anthropic/claude-opus-4-5" → providers.anthropic
   ```

2. **关键词匹配**
   模型名称包含提供商的关键词（按 PROVIDERS 注册顺序）
   ```json
   "model": "gpt-4"           → providers.openai (关键词: "gpt")
   "model": "claude-3-opus"   → providers.anthropic (关键词: "claude")
   "model": "qwen-max"        → providers.dashscope (关键词: "qwen")
   ```

3. **网关回退**
   未匹配到标准提供商时，使用第一个有 API Key 的网关提供商（OpenRouter, AiHubMix, SiliconFlow, VolcEngine）
   ```json
   "model": "unknown-model"
   → 使用 providers.openrouter（如果有 apiKey）
   ```

4. **默认回退**
   使用第一个有 API Key 的任意提供商（OAuth 提供商除外）

#### 匹配逻辑代码位置
- `nanobot/config/schema.py:299-334` - `_match_provider()` 方法
- `nanobot/providers/registry.py:72-399` - PROVIDERS 注册表

### 3.2 通用字段说明

所有提供商配置共享以下三个字段：

#### `apiKey`

**类型**: `string`
**默认值**: `""` (空字符串)
**用途**: LLM 提供商的 API 密钥

**详细说明**:
- **功能描述**: 用于身份验证的 API 密钥，大多数提供商必需
- **使用场景**: 所有需要 API 访问的提供商（除 OAuth 类型）
- **配置要求**:
  - 直连类提供商（Anthropic, OpenAI）：必需
  - 网关类提供商（OpenRouter）：必需
  - 本地类提供商（vLLM）：可选
  - OAuth 类提供商（github_copilot）：不适用

**配置示例**:
```json
{
  "providers": {
    "anthropic": {
      "apiKey": "sk-ant-api03-YOUR_KEY_HERE"
    },
    "openai": {
      "apiKey": "sk-proj-YOUR_KEY_HERE"
    }
  }
}
```

**注意事项**:
- ⚠️ **安全警告**:
  - 切勿将 API Key 提交到版本控制系统
  - 优先使用环境变量：`export NANOBOT_PROVIDERS__ANTHROPIC__API_KEY="sk-xxx"`
  - 生产环境使用密钥管理服务（如 AWS Secrets Manager）
- 🔗 **相关配置**: [`agents.defaults.model`](#model) - 模型名称决定使用哪个提供商

---

#### `apiBase`

**类型**: `string | null`
**默认值**: `null`
**用途**: 自定义 API 端点 URL

**详细说明**:
- **功能描述**: 覆盖提供商的默认 API 端点，用于代理、自托管或网关服务
- **使用场景**:
  - 企业内网代理：将请求路由到内网网关
  - 自托管模型：指向本地 vLLM 服务
  - 网关服务：使用 OpenRouter, AiHubMix 等第三方网关
  - 区域优化：使用特定区域的 API 端点（如 Moonshot 中国区 `api.moonshot.cn`）
- **配置要求**:
  - 必须是完整的 HTTP(S) URL
  - 通常以 `/v1` 结尾（OpenAI 兼容）
  - 网关类提供商有默认值（见下表）

**默认 apiBase 值（网关类提供商）**:
| 提供商 | 默认 apiBase |
|-------|-------------|
| OpenRouter | `https://openrouter.ai/api/v1` |
| AiHubMix | `https://aihubmix.com/v1` |
| SiliconFlow | `https://api.siliconflow.cn/v1` |
| VolcEngine | `https://ark.cn-beijing.volces.com/api/v3` |
| Moonshot | `https://api.moonshot.ai/v1` |
| MiniMax | `https://api.minimax.io/v1` |

**配置示例**:
```json
{
  "providers": {
    "vllm": {
      "apiBase": "http://localhost:8000/v1",
      "apiKey": "dummy"
    },
    "openai": {
      "apiBase": "https://api.openai-proxy.com/v1",
      "apiKey": "sk-xxx"
    }
  }
}
```

**注意事项**:
- 📊 **推荐值**:
  - 本地 vLLM: `http://localhost:8000/v1`
  - Moonshot 中国: `https://api.moonshot.cn/v1`
- 🔗 **相关配置**: `providers.*.extraHeaders` - 某些代理需要额外请求头

---

#### `extraHeaders`

**类型**: `dict[string, string] | null`
**默认值**: `null`
**用途**: 自定义 HTTP 请求头

**详细说明**:
- **功能描述**: 在每次 LLM API 请求中添加自定义 HTTP 头部
- **使用场景**:
  - AiHubMix 网关：需要 `APP-Code` 头部标识应用
  - 企业代理：添加内部认证 Token
  - A/B 测试：添加实验标识头部
- **配置要求**:
  - JSON 对象，键值对都是字符串
  - 头部名称大小写不敏感（HTTP 标准）

**配置示例**:
```json
{
  "providers": {
    "aihubmix": {
      "apiKey": "sk-xxx",
      "apiBase": "https://aihubmix.com/v1",
      "extraHeaders": {
        "APP-Code": "your-app-code-here"
      }
    },
    "custom": {
      "apiKey": "internal-token",
      "apiBase": "https://internal-gateway.company.com/v1",
      "extraHeaders": {
        "X-Internal-Auth": "bearer-token-here",
        "X-Environment": "production"
      }
    }
  }
}
```

**注意事项**:
- ⚠️ **安全警告**:
  - 避免在配置文件中硬编码敏感 Token
  - 优先使用环境变量：
    ```bash
    export NANOBOT_PROVIDERS__CUSTOM__EXTRA_HEADERS__X_INTERNAL_AUTH="bearer-xxx"
    ```
- 🔗 **典型用例**: AiHubMix 要求 `APP-Code` 头部用于应用识别

---

### 3.3 提供商分类详解

Nanobot 支持 17 个提供商，分为 4 大类：

#### 3.3.1 直连类提供商（9 个）

直接连接到官方 API，无需中间网关。

##### Anthropic

**关键词**: `anthropic`, `claude`
**环境变量**: `ANTHROPIC_API_KEY`
**支持功能**: ✅ Prompt Caching (提示词缓存)

**配置示例**:
```json
{
  "providers": {
    "anthropic": {
      "apiKey": "sk-ant-api03-YOUR_KEY_HERE"
    }
  },
  "agents": {
    "defaults": {
      "model": "claude-opus-4-5"
    }
  }
}
```

**说明**:
- 官方 API，无需 `litellm_prefix`（LiteLLM 原生支持）
- 支持 `claude-3-opus`, `claude-3-sonnet`, `claude-opus-4-5` 等
- 支持 Prompt Caching 功能，可大幅降低成本

---

##### OpenAI

**关键词**: `openai`, `gpt`
**环境变量**: `OPENAI_API_KEY`

**配置示例**:
```json
{
  "providers": {
    "openai": {
      "apiKey": "sk-proj-YOUR_KEY_HERE"
    }
  },
  "agents": {
    "defaults": {
      "model": "gpt-4"
    }
  }
}
```

**说明**:
- 官方 API，无需 `litellm_prefix`
- 支持 `gpt-4`, `gpt-4-turbo`, `gpt-3.5-turbo` 等

---

##### DeepSeek

**关键词**: `deepseek`
**环境变量**: `DEEPSEEK_API_KEY`
**LiteLLM 前缀**: `deepseek/`

**配置示例**:
```json
{
  "providers": {
    "deepseek": {
      "apiKey": "sk-YOUR_KEY_HERE"
    }
  },
  "agents": {
    "defaults": {
      "model": "deepseek/deepseek-chat"
    }
  }
}
```

**说明**:
- 高性价比模型，适合代码生成
- 模型会自动添加 `deepseek/` 前缀（如 `deepseek-chat` → `deepseek/deepseek-chat`）
- 已包含前缀时不重复添加（`deepseek/xxx` 保持不变）

---

##### Gemini

**关键词**: `gemini`
**环境变量**: `GEMINI_API_KEY`
**LiteLLM 前缀**: `gemini/`

**配置示例**:
```json
{
  "providers": {
    "gemini": {
      "apiKey": "AIzaSyXXXXXXXXX"
    }
  },
  "agents": {
    "defaults": {
      "model": "gemini/gemini-pro"
    }
  }
}
```

---

##### Zhipu AI (智谱)

**关键词**: `zhipu`, `glm`, `zai`
**环境变量**: `ZAI_API_KEY`, `ZHIPUAI_API_KEY` (镜像)
**LiteLLM 前缀**: `zai/`

**配置示例**:
```json
{
  "providers": {
    "zhipu": {
      "apiKey": "YOUR_KEY.HERE"
    }
  },
  "agents": {
    "defaults": {
      "model": "glm-4"
    }
  }
}
```

**说明**:
- API Key 会同时设置到 `ZAI_API_KEY` 和 `ZHIPUAI_API_KEY`
- 模型自动添加 `zai/` 前缀（`glm-4` → `zai/glm-4`）

---

##### DashScope (通义千问)

**关键词**: `qwen`, `dashscope`
**环境变量**: `DASHSCOPE_API_KEY`
**LiteLLM 前缀**: `dashscope/`

**配置示例**:
```json
{
  "providers": {
    "dashscope": {
      "apiKey": "sk-YOUR_KEY_HERE"
    }
  },
  "agents": {
    "defaults": {
      "model": "qwen-max"
    }
  }
}
```

---

##### Moonshot (月之暗面 Kimi)

**关键词**: `moonshot`, `kimi`
**环境变量**: `MOONSHOT_API_KEY`, `MOONSHOT_API_BASE`
**LiteLLM 前缀**: `moonshot/`
**默认 API Base**: `https://api.moonshot.ai/v1`

**配置示例**:
```json
{
  "providers": {
    "moonshot": {
      "apiKey": "sk-YOUR_KEY_HERE",
      "apiBase": "https://api.moonshot.cn/v1"
    }
  },
  "agents": {
    "defaults": {
      "model": "kimi-k2.5"
    }
  }
}
```

**注意事项**:
- ⚠️ **特殊限制**: Kimi K2.5 模型强制 `temperature >= 1.0`（由系统自动处理）
- 🔗 **区域选择**:
  - 国际: `https://api.moonshot.ai/v1`
  - 中国: `https://api.moonshot.cn/v1`

---

##### MiniMax

**关键词**: `minimax`
**环境变量**: `MINIMAX_API_KEY`
**LiteLLM 前缀**: `minimax/`
**默认 API Base**: `https://api.minimax.io/v1`

**配置示例**:
```json
{
  "providers": {
    "minimax": {
      "apiKey": "YOUR_KEY_HERE"
    }
  },
  "agents": {
    "defaults": {
      "model": "MiniMax-M2.1"
    }
  }
}
```

---

##### Groq

**关键词**: `groq`
**环境变量**: `GROQ_API_KEY`
**LiteLLM 前缀**: `groq/`

**配置示例**:
```json
{
  "providers": {
    "groq": {
      "apiKey": "gsk_YOUR_KEY_HERE"
    }
  },
  "agents": {
    "defaults": {
      "model": "groq/llama3-8b-8192"
    }
  }
}
```

**说明**:
- 主要用于 Whisper 语音转录，也支持 LLM 推理
- 提供高速推理服务

---

#### 3.3.2 网关类提供商（4 个）

路由任意模型，通常支持多家 LLM 提供商。

##### OpenRouter

**关键词**: `openrouter`
**环境变量**: `OPENROUTER_API_KEY`
**API Key 前缀**: `sk-or-` (自动检测)
**默认 API Base**: `https://openrouter.ai/api/v1`
**支持功能**: ✅ Prompt Caching

**配置示例**:
```json
{
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-YOUR_KEY_HERE"
    }
  },
  "agents": {
    "defaults": {
      "model": "anthropic/claude-opus-4-5"
    }
  }
}
```

**说明**:
- 支持 100+ 种模型，自动路由到对应提供商
- 模型名称格式: `provider/model`（如 `anthropic/claude-opus-4-5`）
- API Key 以 `sk-or-` 开头时自动识别为 OpenRouter

---

##### AiHubMix

**关键词**: `aihubmix`
**环境变量**: `OPENAI_API_KEY` (OpenAI 兼容)
**默认 API Base**: `https://aihubmix.com/v1`
**LiteLLM 前缀**: `openai/`
**特殊行为**: `strip_model_prefix: true`

**配置示例**:
```json
{
  "providers": {
    "aihubmix": {
      "apiKey": "sk-YOUR_KEY_HERE",
      "apiBase": "https://aihubmix.com/v1",
      "extraHeaders": {
        "APP-Code": "your-app-code"
      }
    }
  },
  "agents": {
    "defaults": {
      "model": "claude-3-opus"
    }
  }
}
```

**注意事项**:
- ⚠️ **必需配置**: `extraHeaders.APP-Code` 用于应用识别
- 🔗 **模型前缀处理**:
  - 输入: `anthropic/claude-3-opus`
  - 处理: 去除 `anthropic/` → `claude-3-opus`
  - 发送: 添加 `openai/` → `openai/claude-3-opus`

---

##### SiliconFlow (硅基流动)

**关键词**: `siliconflow`
**环境变量**: `OPENAI_API_KEY` (OpenAI 兼容)
**默认 API Base**: `https://api.siliconflow.cn/v1`
**LiteLLM 前缀**: `openai/`

**配置示例**:
```json
{
  "providers": {
    "siliconflow": {
      "apiKey": "sk-YOUR_KEY_HERE",
      "apiBase": "https://api.siliconflow.cn/v1"
    }
  },
  "agents": {
    "defaults": {
      "model": "deepseek/deepseek-chat"
    }
  }
}
```

---

##### VolcEngine (火山引擎)

**关键词**: `volcengine`, `volces`, `ark`
**环境变量**: `OPENAI_API_KEY` (OpenAI 兼容)
**默认 API Base**: `https://ark.cn-beijing.volces.com/api/v3`
**LiteLLM 前缀**: `volcengine/`

**配置示例**:
```json
{
  "providers": {
    "volcengine": {
      "apiKey": "YOUR_KEY_HERE",
      "apiBase": "https://ark.cn-beijing.volces.com/api/v3"
    }
  },
  "agents": {
    "defaults": {
      "model": "doubao-pro"
    }
  }
}
```

---

#### 3.3.3 本地类提供商（2 个）

##### vLLM / Local

**关键词**: `vllm`
**环境变量**: `HOSTED_VLLM_API_KEY` (可选)
**LiteLLM 前缀**: `hosted_vllm/`

**配置示例**:
```json
{
  "providers": {
    "vllm": {
      "apiBase": "http://localhost:8000/v1",
      "apiKey": "dummy"
    }
  },
  "agents": {
    "defaults": {
      "model": "Llama-3-8B"
    }
  }
}
```

**说明**:
- `apiKey` 可选（本地服务通常不需要）
- `apiBase` 必需，指向本地 vLLM 服务
- 模型名称直接使用本地部署的模型名

---

##### Custom

**关键词**: 无（直连类型）
**Is Direct**: `true` (绕过 LiteLLM)

**配置示例**:
```json
{
  "providers": {
    "custom": {
      "apiBase": "https://custom-llm-api.company.com/v1",
      "apiKey": "internal-token",
      "extraHeaders": {
        "X-Custom-Header": "value"
      }
    }
  },
  "agents": {
    "defaults": {
      "model": "custom-model-name"
    }
  }
}
```

**说明**:
- 用于任何 OpenAI 兼容的自定义端点
- 绕过 LiteLLM，直接使用 OpenAI SDK
- 适合企业内部自研 LLM API

---

#### 3.3.4 OAuth 类提供商（2 个）

使用 OAuth 认证，无需 API Key。

##### OpenAI Codex

**关键词**: `openai-codex`, `codex`
**默认 API Base**: `https://chatgpt.com/backend-api`
**Is OAuth**: `true`

**配置示例**:
```json
{
  "providers": {
    "openai_codex": {
      "apiBase": "https://chatgpt.com/backend-api"
    }
  },
  "agents": {
    "defaults": {
      "model": "codex"
    }
  }
}
```

**说明**:
- 使用 OAuth 流程认证，不需要 `apiKey`
- 需要用户授权登录

---

##### Github Copilot

**关键词**: `github_copilot`, `copilot`
**LiteLLM 前缀**: `github_copilot/`
**Is OAuth**: `true`

**配置示例**:
```json
{
  "providers": {
    "github_copilot": {}
  },
  "agents": {
    "defaults": {
      "model": "github_copilot/gpt-4"
    }
  }
}
```

**说明**:
- 使用 OAuth 流程认证，不需要 `apiKey`
- 需要 GitHub Copilot 订阅

---

### 3.4 故障排查

| 问题 | 可能原因 | 解决方案 |
|-----|---------|---------|
| `No API key configured` | 未配置 API Key | 检查 `providers.*.apiKey` 或环境变量 `NANOBOT_PROVIDERS__*__API_KEY` |
| `Model not found` | 模型名称错误或不支持 | 检查模型名称拼写，参考提供商官方文档 |
| `Authentication failed` | API Key 无效或过期 | 重新生成 API Key，检查是否正确复制 |
| `Connection timeout` | API Base 错误或网络问题 | 检查 `apiBase` 配置，测试网络连通性 |
| `Provider mismatch` | 模型匹配到错误的提供商 | 使用显式前缀（如 `deepseek/deepseek-chat`） |
| `Rate limit exceeded` | 超过 API 调用频率限制 | 降低请求频率，升级 API 套餐 |
| `Invalid extra headers` | AiHubMix 缺少 APP-Code | 添加 `extraHeaders: {"APP-Code": "xxx"}` |
| `Temperature out of range` | Moonshot Kimi K2.5 要求 >= 1.0 | 系统自动处理，无需手动调整 |

**调试建议**:
1. 使用 `nanobot status` 命令检查提供商状态
2. 查看日志文件（通常在 `~/.nanobot/logs/`）
3. 测试 API Key: `curl` 直接调用提供商 API
4. 检查环境变量优先级（环境变量会覆盖配置文件）

---

## 四、聊天渠道配置 (Channels)

聊天渠道（Channel）定义了 nanobot 如何与各种通讯平台集成。

### 4.1 全局配置

#### `sendProgress`

**类型**: `bool`
**默认值**: `true`
**用途**: 是否向渠道实时推送 Agent 处理进度

**详细说明**:
- **功能描述**: 控制是否将 Agent 的思考过程和工作进度实时推送给用户
- **使用场景**:
  - 启用（`true`）：用户可以看到"正在读取文件..."、"正在生成代码..."等进度提示
  - 禁用（`false`）：只发送最终结果，减少消息推送频率
- **配置要求**: 影响所有已启用的渠道

**配置示例**:
```json
{
  "channels": {
    "sendProgress": false
  }
}
```

**代码使用位置**:
- `nanobot/cli/commands.py:222-227` - CLI 进度回调中检查此配置
- `nanobot/agent/loop.py:220` - 传递给渠道配置

---

#### `sendToolHints`

**类型**: `bool`
**默认值**: `false`
**用途**: 是否推送工具调用提示（如 `read_file("path.py")`）

**详细说明**:
- **功能描述**: 控制是否显示工具调用的详细参数
- **使用场景**:
  - 启用（`true`）：调试模式，查看 Agent 具体调用了哪些工具
  - 禁用（`false`）：隐藏技术细节，提升用户体验
- **配置要求**: 通常仅在开发调试时启用

**配置示例**:
```json
{
  "channels": {
    "sendToolHints": true
  }
}
```

**代码使用位置**:
- `nanobot/cli/commands.py:223-226` - CLI 进度回调中检查此配置

---

### 4.2 渠道分类表

| 渠道 | 类型 | 配置复杂度 | 典型用途 | 必需字段数 |
|-----|------|----------|---------|-----------|
| **Telegram** | 即时通讯 | ⭐ 简单 | 个人助手、快速问答 | 2 (token, enabled) |
| **WhatsApp** | 即时通讯 | ⭐⭐ 中等 | 海外用户交互 | 3 (bridgeUrl, bridgeToken, enabled) |
| **Discord** | 社区平台 | ⭐ 简单 | 开发者社区、技术支持 | 2 (token, enabled) |
| **Slack** | 企业协作 | ⭐⭐⭐ 复杂 | 企业内部助手、工作流集成 | 3 (botToken, appToken, enabled) |
| **Feishu** | 企业协作 | ⭐⭐ 中等 | 国内企业内网 | 3 (appId, appSecret, enabled) |
| **DingTalk** | 企业协作 | ⭐ 简单 | 国内企业钉钉集成 | 3 (clientId, clientSecret, enabled) |
| **Email** | 异步消息 | ⭐⭐⭐⭐ 最复杂 | 正式沟通、记录留档 | 13 (IMAP+SMTP 完整配置) |
| **Mochat** | 企业微信 | ⭐⭐⭐ 复杂 | 企业微信私有化部署 | 5 (baseUrl, clawToken, agentUserId, enabled) |
| **QQ** | 即时通讯 | ⭐ 简单 | QQ 频道机器人 | 3 (appId, secret, enabled) |

### 4.3 各渠道详细配置

#### 4.3.1 Telegram

**配置复杂度**: ⭐ 简单
**适用场景**: 个人助手、跨境通信、快速原型

**字段说明**:

##### `enabled`
**类型**: `bool` | **默认值**: `false`
**用途**: 是否启用 Telegram 渠道

##### `token`
**类型**: `string` | **默认值**: `""`
**用途**: Telegram Bot Token（从 @BotFather 获取）

**获取方式**:
1. 在 Telegram 中搜索 `@BotFather`
2. 发送 `/newbot` 创建新机器人
3. 按提示设置名称和用户名
4. 复制返回的 Token（格式: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz-1234567890`）

##### `allowFrom`
**类型**: `list[string]` | **默认值**: `[]`
**用途**: 白名单用户 ID 或用户名列表

**详细说明**:
- 空列表 `[]` = 公开访问（任何人都可以使用）
- 非空列表 = 仅白名单用户可访问
- 用户标识格式:
  - 数字 ID: `"123456789"` (推荐，从 `/start` 命令或 `@userinfobot` 获取)
  - 用户名: `"@username"` (不推荐，用户可随时更改)

##### `proxy`
**类型**: `string | null` | **默认值**: `null`
**用途**: HTTP/SOCKS5 代理地址

**格式**:
- HTTP 代理: `"http://127.0.0.1:7890"`
- SOCKS5 代理: `"socks5://127.0.0.1:1080"`

##### `replyToMessage`
**类型**: `bool` | **默认值**: `false`
**用途**: 是否回复时引用原始消息

**完整配置示例**:
```json
{
  "channels": {
    "telegram": {
      "enabled": true,
      "token": "YOUR_TELEGRAM_BOT_TOKEN",
      "allowFrom": ["123456789", "987654321"],
      "proxy": "http://127.0.0.1:7890",
      "replyToMessage": true
    }
  }
}
```

**注意事项**:
- ⚠️ **安全警告**: Token 泄露会导致机器人被劫持，务必保密
- 🔗 **推荐配置**: 生产环境必须设置 `allowFrom` 白名单
- 📊 **性能**: Telegram 使用长轮询（long polling），无需公网 IP

**代码使用位置**:
- `nanobot/channels/telegram.py:24-31` - 配置类定义
- `nanobot/channels/telegram.py:101-115` - 白名单验证逻辑

---

#### 4.3.2 Discord

**配置复杂度**: ⭐ 简单
**适用场景**: 开发者社区、游戏社群、技术支持

**字段说明**:

##### `enabled`
**类型**: `bool` | **默认值**: `false`

##### `token`
**类型**: `string` | **默认值**: `""`
**用途**: Discord Bot Token（从 Discord Developer Portal 获取）

**获取方式**:
1. 访问 https://discord.com/developers/applications
2. 创建新应用（New Application）
3. 进入 Bot 页面，点击 Add Bot
4. 复制 Token

##### `allowFrom`
**类型**: `list[string]` | **默认值**: `[]`
**用途**: 白名单用户 ID 列表（18位数字）

##### `gatewayUrl`
**类型**: `string` | **默认值**: `"wss://gateway.discord.gg/?v=10&encoding=json"`
**用途**: Discord Gateway WebSocket URL（通常无需修改）

##### `intents`
**类型**: `int` | **默认值**: `37377`
**用途**: 权限位掩码（GUILDS + GUILD_MESSAGES + DIRECT_MESSAGES + MESSAGE_CONTENT）

**完整配置示例**:
```json
{
  "channels": {
    "discord": {
      "enabled": true,
      "token": "YOUR_DISCORD_BOT_TOKEN_HERE",
      "allowFrom": ["123456789012345678"]
    }
  }
}
```

**注意事项**:
- ⚠️ **重要**: 必须在 Discord Developer Portal 启用 `MESSAGE CONTENT INTENT`
- 📊 **推荐值**: `intents: 37377` 已包含所有必需权限

---

#### 4.3.3 Slack

**配置复杂度**: ⭐⭐⭐ 复杂
**适用场景**: 企业内部协作、工作流自动化

**字段说明**:

##### `enabled`
**类型**: `bool` | **默认值**: `false`

##### `mode`
**类型**: `string` | **默认值**: `"socket"`
**用途**: 连接模式（目前仅支持 Socket Mode）

##### `botToken`
**类型**: `string` | **默认值**: `""`
**用途**: Bot User OAuth Token（以 `xoxb-` 开头）

##### `appToken`
**类型**: `string` | **默认值**: `""`
**用途**: App-Level Token（以 `xapp-` 开头，用于 Socket Mode）

**获取方式**:
1. 访问 https://api.slack.com/apps 创建应用
2. 启用 Socket Mode，生成 App-Level Token
3. 安装应用到工作区，获取 Bot User OAuth Token

##### `replyInThread`
**类型**: `bool` | **默认值**: `true`
**用途**: 是否在消息线程中回复（保持对话上下文）

##### `reactEmoji`
**类型**: `string` | **默认值**: `"eyes"`
**用途**: 收到消息时添加的 emoji 反应（表示已读）

##### `groupPolicy`
**类型**: `string` | **默认值**: `"mention"`
**用途**: 频道群组策略

**可选值**:
- `"mention"`: 仅响应 @机器人 的消息
- `"open"`: 响应频道所有消息
- `"allowlist"`: 仅响应白名单频道（配合 `groupAllowFrom`）

##### `groupAllowFrom`
**类型**: `list[string]` | **默认值**: `[]`
**用途**: 白名单频道 ID 列表（当 `groupPolicy="allowlist"` 时使用）

##### `dm`
**类型**: `object` | 嵌套配置对象

###### `dm.enabled`
**类型**: `bool` | **默认值**: `true`
**用途**: 是否允许私信（DM）

###### `dm.policy`
**类型**: `string` | **默认值**: `"open"`
**可选值**: `"open"` (所有人) | `"allowlist"` (仅白名单)

###### `dm.allowFrom`
**类型**: `list[string]` | **默认值**: `[]`
**用途**: 私信白名单用户 ID 列表

**完整配置示例**:
```json
{
  "channels": {
    "slack": {
      "enabled": true,
      "mode": "socket",
      "botToken": "xoxb-YOUR-BOT-TOKEN-HERE",
      "appToken": "xapp-YOUR-APP-TOKEN-HERE",
      "replyInThread": true,
      "reactEmoji": "robot_face",
      "groupPolicy": "mention",
      "groupAllowFrom": [],
      "dm": {
        "enabled": true,
        "policy": "allowlist",
        "allowFrom": ["U01234ABCDE", "U98765FGHIJ"]
      }
    }
  }
}
```

**注意事项**:
- ⚠️ **权限要求**: 必须在 Slack App 配置中启用以下 Bot Token Scopes:
  - `channels:history`
  - `chat:write`
  - `im:history`
  - `reactions:write`
- 🔗 **Socket Mode**: 无需公网 IP，适合企业内网部署
- 📊 **推荐策略**: 频道使用 `mention` 策略，避免噪音干扰

---

#### 4.3.4 Email

**配置复杂度**: ⭐⭐⭐⭐ 最复杂
**适用场景**: 正式沟通、审计留档、异步协作

**字段说明**:

##### `enabled`
**类型**: `bool` | **默认值**: `false`

##### `consentGranted`
**类型**: `bool` | **默认值**: `false`
**用途**: 用户显式授权访问邮箱（隐私保护设计）

**详细说明**:
- ⚠️ **必需确认**: 此字段必须设置为 `true` 才能启用 Email 渠道
- 用于明确用户同意 nanobot 访问邮箱数据
- 合规考虑：GDPR、CCPA 等隐私法规要求

**IMAP 配置（接收邮件）**:

##### `imapHost`
**类型**: `string` | **默认值**: `""`
**示例**: `"imap.gmail.com"`, `"outlook.office365.com"`

##### `imapPort`
**类型**: `int` | **默认值**: `993`
**说明**: IMAP over SSL 标准端口为 993

##### `imapUsername`
**类型**: `string` | **默认值**: `""`
**说明**: 邮箱完整地址（如 `user@example.com`）

##### `imapPassword`
**类型**: `string` | **默认值**: `""`
**说明**: 邮箱密码或应用专用密码

**注意**: Gmail / Outlook 需要生成应用专用密码:
- Gmail: https://myaccount.google.com/apppasswords
- Outlook: https://account.live.com/proofs/AppPassword

##### `imapMailbox`
**类型**: `string` | **默认值**: `"INBOX"`
**说明**: 监控的邮箱文件夹名称

##### `imapUseSsl`
**类型**: `bool` | **默认值**: `true`
**说明**: 是否使用 SSL/TLS 加密连接

**SMTP 配置（发送邮件）**:

##### `smtpHost`
**类型**: `string` | **默认值**: `""`
**示例**: `"smtp.gmail.com"`, `"smtp-mail.outlook.com"`

##### `smtpPort`
**类型**: `int` | **默认值**: `587`
**说明**: SMTP with STARTTLS 标准端口为 587（SSL 端口为 465）

##### `smtpUsername`
**类型**: `string` | **默认值**: `""`

##### `smtpPassword`
**类型**: `string` | **默认值**: `""`

##### `smtpUseTls`
**类型**: `bool` | **默认值**: `true`
**说明**: 是否使用 STARTTLS 升级连接

##### `smtpUseSsl`
**类型**: `bool` | **默认值**: `false`
**说明**: 是否直接使用 SSL（端口 465）

##### `fromAddress`
**类型**: `string` | **默认值**: `""`
**说明**: 发件人地址（通常与 `smtpUsername` 相同）

**行为配置**:

##### `autoReplyEnabled`
**类型**: `bool` | **默认值**: `true`
**说明**: 是否自动回复邮件（`false` 时仅接收不回复）

##### `pollIntervalSeconds`
**类型**: `int` | **默认值**: `30`
**说明**: IMAP 轮询间隔（秒）

##### `markSeen`
**类型**: `bool` | **默认值**: `true`
**说明**: 是否将处理过的邮件标记为已读

##### `maxBodyChars`
**类型**: `int` | **默认值**: `12000`
**说明**: 邮件正文最大字符数（防止超长邮件）

##### `subjectPrefix`
**类型**: `string` | **默认值**: `"Re: "`
**说明**: 回复邮件主题前缀

##### `allowFrom`
**类型**: `list[string]` | **默认值**: `[]`
**说明**: 白名单发件人邮箱列表

**完整配置示例（Gmail）**:
```json
{
  "channels": {
    "email": {
      "enabled": true,
      "consentGranted": true,
      "imapHost": "imap.gmail.com",
      "imapPort": 993,
      "imapUsername": "your-email@gmail.com",
      "imapPassword": "your-app-password",
      "imapMailbox": "INBOX",
      "imapUseSsl": true,
      "smtpHost": "smtp.gmail.com",
      "smtpPort": 587,
      "smtpUsername": "your-email@gmail.com",
      "smtpPassword": "your-app-password",
      "smtpUseTls": true,
      "smtpUseSsl": false,
      "fromAddress": "your-email@gmail.com",
      "autoReplyEnabled": true,
      "pollIntervalSeconds": 60,
      "markSeen": true,
      "maxBodyChars": 12000,
      "subjectPrefix": "Re: ",
      "allowFrom": ["colleague@company.com", "boss@company.com"]
    }
  }
}
```

**常见邮箱配置**:

| 邮箱服务 | IMAP Host | IMAP Port | SMTP Host | SMTP Port |
|---------|-----------|-----------|-----------|-----------|
| Gmail | `imap.gmail.com` | 993 | `smtp.gmail.com` | 587 |
| Outlook/Hotmail | `outlook.office365.com` | 993 | `smtp-mail.outlook.com` | 587 |
| QQ Mail | `imap.qq.com` | 993 | `smtp.qq.com` | 587 |
| 163 Mail | `imap.163.com` | 993 | `smtp.163.com` | 465 |

**注意事项**:
- ⚠️ **隐私警告**: `consentGranted` 必须为 `true`
- ⚠️ **安全警告**: 使用应用专用密码，不要使用账户主密码
- 🔗 **推荐配置**: 设置 `allowFrom` 白名单，防止垃圾邮件
- 📊 **性能建议**: `pollIntervalSeconds` 不要低于 30 秒，避免频繁轮询

**代码使用位置**:
- `nanobot/channels/email.py:64-68` - `consentGranted` 检查
- `nanobot/channels/email.py:76-98` - IMAP 轮询逻辑

---

#### 4.3.5 其他渠道（简要说明）

##### WhatsApp
- 需要外部 Bridge 服务（如 whatsapp-web.js）
- `bridgeUrl`: WebSocket 桥接地址
- `bridgeToken`: 桥接认证 Token
- `allowFrom`: 白名单电话号码列表

##### Feishu (飞书)
- 使用 WebSocket 长连接模式
- `appId`: 飞书开放平台 App ID
- `appSecret`: 飞书 App Secret
- `encryptKey`: 事件订阅加密 Key（可选）
- `verificationToken`: 事件订阅验证 Token（可选）

##### DingTalk (钉钉)
- 使用 Stream 模式（无需公网 IP）
- `clientId`: 钉钉 AppKey
- `clientSecret`: 钉钉 AppSecret

##### Mochat (企业微信私有化)
- `baseUrl`: Mochat 服务器地址
- `clawToken`: Claw 认证 Token
- `agentUserId`: 代理用户 ID
- `sessions`: 监听的会话列表
- `panels`: 监听的面板列表

##### QQ
- `appId`: QQ 频道机器人 AppID
- `secret`: QQ 频道机器人密钥

---

### 4.4 权限控制说明

所有渠道都支持 `allowFrom` 白名单机制，统一逻辑如下：

**白名单规则**:
- `allowFrom: []` (空数组) = **公开访问**，任何人都可以使用
- `allowFrom: ["id1", "id2"]` (非空数组) = **仅白名单**，只有列表中的用户可访问

**用户标识格式（按渠道）**:
| 渠道 | 用户标识格式 | 示例 | 获取方式 |
|-----|-------------|------|---------|
| Telegram | 数字 ID (推荐) 或 @用户名 | `"123456789"`, `"@username"` | `/start` 命令或 `@userinfobot` |
| Discord | 18位数字 ID | `"123456789012345678"` | 右键用户 → 复制 ID（需启用开发者模式） |
| Slack | 用户 ID (U 开头) | `"U01234ABCDE"` | 用户资料 → 更多 → 复制成员 ID |
| Email | 邮箱地址 | `"user@example.com"` | 发件人地址 |
| Feishu | Open ID | `"ou_xxxx"` | 飞书管理后台查看 |
| DingTalk | Staff ID | `"123456"` | 钉钉管理后台查看 |
| WhatsApp | 电话号码 | `"+86123456789"` | 国际格式电话号码 |
| QQ | Open ID | `"xxxx"` | QQ 频道管理后台 |

**安全最佳实践**:
1. ⚠️ **生产环境必须设置白名单**（除非明确需要公开访问）
2. ⚠️ **定期审查白名单**，移除离职人员或不再需要访问的用户
3. ⚠️ **敏感环境使用多重验证**：结合 `allowFrom` + `tools.restrictToWorkspace`
4. 🔗 **日志审计**：记录所有消息来源，便于追溯

**代码使用位置**:
- 所有渠道实现中都有类似逻辑检查 `allowFrom`（如 `telegram.py`, `slack.py`）

---

## 五、工具配置 (Tools)

工具（Tools）定义了 Agent 可以使用的外部能力（如 Web 搜索、Shell 执行、MCP 服务器）。

### 5.1 Web 搜索工具

#### `web.search.apiKey`

**类型**: `string`
**默认值**: `""`
**用途**: Brave Search API 密钥

**详细说明**:
- **功能描述**: 启用 Agent 的 Web 搜索能力（使用 Brave Search API）
- **使用场景**:
  - 实时信息查询（新闻、天气、股价）
  - 技术文档搜索
  - 事实核查
- **配置要求**:
  - 注册 Brave Search API: https://brave.com/search/api/
  - 免费额度: 2,000 次查询/月（2024年标准）

**获取方式**:
1. 访问 https://brave.com/search/api/
2. 注册账户并创建 API Key
3. 复制密钥

#### `web.search.maxResults`

**类型**: `int`
**默认值**: `5`
**用途**: 每次搜索返回的最大结果数

**详细说明**:
- 范围: 1 - 20
- 越多结果消耗越多 tokens
- 推荐值: 3 - 10

**完整配置示例**:
```json
{
  "tools": {
    "web": {
      "search": {
        "apiKey": "BSA-xxx-yyy-zzz",
        "maxResults": 5
      }
    }
  }
}
```

**代码使用位置**:
- `nanobot/agent/tools/web.py` - WebSearchTool 实现
- `nanobot/agent/loop.py:116` - 传递 brave_api_key 到 AgentLoop

---

### 5.2 Shell 执行工具

#### `exec.timeout`

**类型**: `int`
**默认值**: `60`
**用途**: Shell 命令执行超时时间（秒）

**详细说明**:
- **功能描述**: 防止命令无限执行，强制超时中断
- **使用场景**:
  - 长时间运行的编译任务：提高到 300 - 600 秒
  - 快速脚本：保持 30 - 60 秒
- **配置要求**: 必须 > 0

**完整配置示例**:
```json
{
  "tools": {
    "exec": {
      "timeout": 120
    }
  }
}
```

**注意事项**:
- ⚠️ **安全提示**: 配合 `restrictToWorkspace` 使用，限制命令访问范围
- 📊 **推荐值**: 普通脚本 60s，编译构建 300s

**代码使用位置**:
- `nanobot/config/schema.py:259-262` - ExecToolConfig 定义
- `nanobot/agent/tools/shell.py` - ExecTool 使用此配置

---

### 5.3 工作空间沙箱

#### `restrictToWorkspace`

**类型**: `bool`
**默认值**: `false`
**用途**: 是否限制所有工具只能访问工作空间目录

**详细说明**:
- **功能描述**: 启用沙箱模式，所有文件和 Shell 工具只能操作 `agents.defaults.workspace` 目录内的文件
- **使用场景**:
  - ✅ **生产环境强烈推荐启用**
  - ✅ 企业内网部署（防止越权访问）
  - ✅ 多租户环境（隔离用户数据）
  - ❌ 开发调试（需要访问全系统）
- **配置要求**: 与 `agents.defaults.workspace` 配合使用

**完整配置示例**:
```json
{
  "agents": {
    "defaults": {
      "workspace": "/opt/nanobot/workspace"
    }
  },
  "tools": {
    "restrictToWorkspace": true
  }
}
```

**安全影响**:
启用后，以下工具受限：
- **ReadFileTool**: 只能读取 workspace 内的文件
- **WriteFileTool**: 只能写入 workspace 内的文件
- **EditFileTool**: 只能编辑 workspace 内的文件
- **ListDirTool**: 只能列出 workspace 内的目录
- **ExecTool**: Shell 命令仍可执行任意操作（需额外限制，如 Docker 容器）

**注意事项**:
- ⚠️ **安全警告**:
  - 此选项**不能完全防止恶意代码执行**（Shell 命令不受限）
  - 生产环境建议结合 Docker 容器或 VM 隔离
  - 配合 `allowFrom` 白名单使用
- 🔗 **相关配置**: `agents.defaults.workspace`
- 📊 **推荐场景**: 企业内网、多用户环境**必须启用**

**代码使用位置**:
- `nanobot/config/schema.py:281` - ToolsConfig 定义
- `nanobot/agent/loop.py:183-187` - 注册工具时传递 `allowed_dir` 参数

---

### 5.4 MCP 外部工具

MCP (Model Context Protocol) 允许 Agent 集成外部工具和服务。

#### `mcpServers`

**类型**: `dict[string, MCPServerConfig]`
**默认值**: `{}`
**用途**: MCP 服务器连接配置字典

**详细说明**:
- **功能描述**: 通过 MCP 协议连接外部工具服务器，扩展 Agent 能力
- **使用场景**:
  - 集成数据库查询工具
  - 连接企业内部 API
  - 使用第三方工具库
- **配置要求**: 支持两种连接模式（stdio 和 HTTP）

#### MCP 连接模式

##### 模式 1: stdio（本地进程通信）

**适用场景**: 本地安装的 MCP 工具（如 npm 包、Python 脚本）

**字段说明**:

###### `command`
**类型**: `string` | **默认值**: `""`
**说明**: 要执行的命令（如 `"npx"`, `"python"`）

###### `args`
**类型**: `list[string]` | **默认值**: `[]`
**说明**: 命令参数列表

###### `env`
**类型**: `dict[string, string]` | **默认值**: `{}`
**说明**: 额外环境变量

**配置示例（stdio）**:
```json
{
  "tools": {
    "mcpServers": {
      "filesystem": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/files"],
        "env": {
          "NODE_ENV": "production"
        },
        "toolTimeout": 30
      },
      "database": {
        "command": "python",
        "args": ["-m", "mcp_server_sqlite", "--db-path", "/data/app.db"],
        "toolTimeout": 60
      }
    }
  }
}
```

---

##### 模式 2: HTTP（远程 HTTP 端点）

**适用场景**: 远程部署的 MCP 服务器、企业内部 API 网关

**字段说明**:

###### `url`
**类型**: `string` | **默认值**: `""`
**说明**: HTTP 端点 URL（支持 SSE 流式响应）

###### `headers`
**类型**: `dict[string, string]` | **默认值**: `{}`
**说明**: 自定义 HTTP 请求头（如认证 Token）

**配置示例（HTTP）**:
```json
{
  "tools": {
    "mcpServers": {
      "enterprise-api": {
        "url": "https://mcp-gateway.company.com/api/mcp",
        "headers": {
          "Authorization": "Bearer internal-token-here",
          "X-Environment": "production"
        },
        "toolTimeout": 45
      }
    }
  }
}
```

---

#### 通用字段

##### `toolTimeout`
**类型**: `int` | **默认值**: `30`
**用途**: MCP 工具调用超时时间（秒）

**详细说明**:
- 防止 MCP 工具无限等待
- 不同工具可设置不同超时（数据库查询 vs 文件操作）

**完整配置示例（混合模式）**:
```json
{
  "tools": {
    "restrictToWorkspace": false,
    "mcpServers": {
      "github": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {
          "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_xxxx"
        },
        "toolTimeout": 30
      },
      "postgres": {
        "command": "python",
        "args": ["-m", "mcp_server_postgres", "--connection-string", "postgresql://user:pass@localhost/db"],
        "toolTimeout": 60
      },
      "internal-tools": {
        "url": "https://tools.company.com/mcp",
        "headers": {
          "X-API-Key": "secret-key"
        },
        "toolTimeout": 45
      }
    }
  }
}
```

**注意事项**:
- ⚠️ **安全警告**:
  - MCP 工具可以执行任意操作，仅连接受信任的服务器
  - 避免在配置文件中硬编码密钥，优先使用环境变量
  - 生产环境必须验证 MCP 服务器证书（HTTPS）
- 🔗 **相关资源**:
  - MCP 规范: https://spec.modelcontextprotocol.io/
  - 官方工具库: https://github.com/modelcontextprotocol
- 📊 **性能建议**: 设置合理的 `toolTimeout`，避免慢查询阻塞

**代码使用位置**:
- `nanobot/config/schema.py:265-274` - MCPServerConfig 定义
- `nanobot/agent/loop.py:199-206` - MCP 连接逻辑
- `nanobot/agent/tools/mcp.py` - MCP 工具实现

---

## 六、网关配置 (Gateway)

网关（Gateway）配置服务器监听地址和心跳服务。

### 6.1 服务器绑定

#### `host`

**类型**: `string`
**默认值**: `"0.0.0.0"`
**用途**: 服务器绑定地址

**详细说明**:
- **功能描述**: 控制 Gateway HTTP 服务器监听的网络接口
- **使用场景**:
  - `"0.0.0.0"` - 监听所有网络接口（默认，允许外部访问）
  - `"127.0.0.1"` - 仅本地访问（安全）
  - `"192.168.1.100"` - 绑定特定内网 IP
- **配置要求**: 有效的 IP 地址或主机名

#### `port`

**类型**: `int`
**默认值**: `18790`
**用途**: 服务器监听端口

**详细说明**:
- 范围: 1024 - 65535（推荐使用非特权端口 >= 1024）
- 确保端口未被占用

**完整配置示例**:
```json
{
  "gateway": {
    "host": "0.0.0.0",
    "port": 8080
  }
}
```

**注意事项**:
- ⚠️ **安全警告**: 公网部署时使用 `"0.0.0.0"` 需配置防火墙和反向代理
- 🔗 **推荐配置**:
  - 开发环境: `"127.0.0.1"` + 默认端口
  - 生产环境: `"0.0.0.0"` + Nginx/Caddy 反向代理

**代码使用位置**:
- `nanobot/config/schema.py:238-243` - GatewayConfig 定义
- `nanobot/cli/commands.py` - Gateway 服务器启动

---

### 6.2 心跳服务

心跳服务（Heartbeat）定期检查是否有待处理任务，防止系统休眠。

#### `heartbeat.enabled`

**类型**: `bool`
**默认值**: `true`
**用途**: 是否启用心跳服务

**详细说明**:
- **功能描述**: 定期向 Agent 发送心跳检查，唤醒可能的休眠任务
- **使用场景**:
  - 启用（`true`）: 适合长期运行的服务器
  - 禁用（`false`）: 临时测试或按需启动

#### `heartbeat.intervalS`

**类型**: `int`
**默认值**: `1800` (30 分钟)
**用途**: 心跳间隔（秒）

**详细说明**:
- 最小值: 60 秒（避免过于频繁）
- 推荐值: 1800 - 3600 秒（30 - 60 分钟）

**完整配置示例**:
```json
{
  "gateway": {
    "host": "0.0.0.0",
    "port": 18790,
    "heartbeat": {
      "enabled": true,
      "intervalS": 1800
    }
  }
}
```

**注意事项**:
- 📊 **性能影响**: 心跳不会触发 LLM 调用，仅检查队列，成本极低
- 🔗 **使用场景**: 主要用于防止长时间无活动导致的连接断开

**代码使用位置**:
- `nanobot/config/schema.py:231-235` - HeartbeatConfig 定义
- `nanobot/heartbeat/service.py` - HeartbeatService 实现

---

## 七、附录

### 附录 A: 配置模板库

#### 模板 1: 最小可用配置

```json
{
  "providers": {
    "anthropic": {
      "apiKey": "sk-ant-api03-YOUR_API_KEY_HERE"
    }
  }
}
```

**用途**: CLI 快速启动，零额外配置

---

#### 模板 2: 个人助手（Telegram + OpenRouter）

```json
{
  "agents": {
    "defaults": {
      "workspace": "~/my-assistant-workspace",
      "model": "anthropic/claude-opus-4-5",
      "maxTokens": 8192,
      "temperature": 0.3,
      "maxToolIterations": 40,
      "memoryWindow": 100
    }
  },
  "providers": {
    "openrouter": {
      "apiKey": "sk-or-v1-YOUR_KEY_HERE"
    }
  },
  "channels": {
    "sendProgress": true,
    "sendToolHints": false,
    "telegram": {
      "enabled": true,
      "token": "YOUR_TELEGRAM_BOT_TOKEN",
      "allowFrom": ["YOUR_TELEGRAM_USER_ID"],
      "proxy": null,
      "replyToMessage": true
    }
  },
  "tools": {
    "web": {
      "search": {
        "apiKey": "BSA-YOUR_BRAVE_API_KEY",
        "maxResults": 5
      }
    },
    "exec": {
      "timeout": 60
    },
    "restrictToWorkspace": false
  }
}
```

**用途**: 个人日常使用，Telegram 私聊助手

---

#### 模板 3: 企业内网（Feishu + 沙箱模式）

```json
{
  "agents": {
    "defaults": {
      "workspace": "/opt/nanobot/workspace",
      "model": "deepseek/deepseek-chat",
      "maxTokens": 8192,
      "temperature": 0.1,
      "maxToolIterations": 40,
      "memoryWindow": 80
    }
  },
  "providers": {
    "deepseek": {
      "apiKey": "sk-YOUR_DEEPSEEK_KEY",
      "apiBase": null
    }
  },
  "channels": {
    "sendProgress": true,
    "sendToolHints": false,
    "feishu": {
      "enabled": true,
      "appId": "cli_xxx",
      "appSecret": "yyy",
      "encryptKey": "",
      "verificationToken": "",
      "allowFrom": ["ou_xxx", "ou_yyy"]
    }
  },
  "tools": {
    "exec": {
      "timeout": 120
    },
    "restrictToWorkspace": true,
    "mcpServers": {}
  },
  "gateway": {
    "host": "0.0.0.0",
    "port": 18790,
    "heartbeat": {
      "enabled": true,
      "intervalS": 1800
    }
  }
}
```

**用途**: 企业内网部署，严格权限控制

---

#### 模板 4: 本地开发（vLLM + 全工具开放）

```json
{
  "agents": {
    "defaults": {
      "workspace": "~/dev/nanobot-workspace",
      "model": "Llama-3-70B-Instruct",
      "maxTokens": 4096,
      "temperature": 0.2,
      "maxToolIterations": 60,
      "memoryWindow": 100
    }
  },
  "providers": {
    "vllm": {
      "apiKey": "dummy",
      "apiBase": "http://localhost:8000/v1"
    }
  },
  "channels": {
    "sendProgress": true,
    "sendToolHints": true
  },
  "tools": {
    "exec": {
      "timeout": 300
    },
    "restrictToWorkspace": false,
    "mcpServers": {
      "github": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "env": {
          "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_xxx"
        },
        "toolTimeout": 30
      }
    }
  }
}
```

**用途**: 本地模型开发调试

---

#### 模板 5: 高安全生产环境

```json
{
  "agents": {
    "defaults": {
      "workspace": "/var/nanobot/workspace",
      "model": "anthropic/claude-sonnet-4-5",
      "maxTokens": 8192,
      "temperature": 0.1,
      "maxToolIterations": 30,
      "memoryWindow": 60
    }
  },
  "providers": {
    "anthropic": {
      "apiKey": "${ANTHROPIC_API_KEY}",
      "apiBase": null
    }
  },
  "channels": {
    "sendProgress": false,
    "sendToolHints": false,
    "slack": {
      "enabled": true,
      "mode": "socket",
      "botToken": "${SLACK_BOT_TOKEN}",
      "appToken": "${SLACK_APP_TOKEN}",
      "replyInThread": true,
      "reactEmoji": "white_check_mark",
      "groupPolicy": "allowlist",
      "groupAllowFrom": ["C01234ABCDE"],
      "dm": {
        "enabled": true,
        "policy": "allowlist",
        "allowFrom": ["U01234ABCDE", "U98765FGHIJ"]
      }
    }
  },
  "tools": {
    "web": {
      "search": {
        "apiKey": "",
        "maxResults": 3
      }
    },
    "exec": {
      "timeout": 60
    },
    "restrictToWorkspace": true,
    "mcpServers": {}
  },
  "gateway": {
    "host": "127.0.0.1",
    "port": 18790,
    "heartbeat": {
      "enabled": true,
      "intervalS": 3600
    }
  }
}
```

**用途**: 生产环境，最大化安全性（注意使用环境变量代替敏感值）

---

### 附录 B: 环境变量映射表

Nanobot 支持通过环境变量覆盖配置文件，格式规则：

**命名规则**: `NANOBOT_` + 大写路径 + `__` 分隔符

**示例映射**:

| 配置文件路径 | 环境变量名称 |
|-------------|------------|
| `agents.defaults.model` | `NANOBOT_AGENTS__DEFAULTS__MODEL` |
| `agents.defaults.maxTokens` | `NANOBOT_AGENTS__DEFAULTS__MAX_TOKENS` |
| `providers.anthropic.apiKey` | `NANOBOT_PROVIDERS__ANTHROPIC__API_KEY` |
| `providers.openai.apiBase` | `NANOBOT_PROVIDERS__OPENAI__API_BASE` |
| `channels.telegram.token` | `NANOBOT_CHANNELS__TELEGRAM__TOKEN` |
| `channels.slack.botToken` | `NANOBOT_CHANNELS__SLACK__BOT_TOKEN` |
| `tools.restrictToWorkspace` | `NANOBOT_TOOLS__RESTRICT_TO_WORKSPACE` |
| `tools.web.search.apiKey` | `NANOBOT_TOOLS__WEB__SEARCH__API_KEY` |
| `gateway.host` | `NANOBOT_GATEWAY__HOST` |
| `gateway.heartbeat.enabled` | `NANOBOT_GATEWAY__HEARTBEAT__ENABLED` |

**嵌套对象（extraHeaders）**:
```bash
export NANOBOT_PROVIDERS__AIHUBMIX__EXTRA_HEADERS__APP_CODE="my-app-code"
```

对应配置:
```json
{
  "providers": {
    "aihubmix": {
      "extraHeaders": {
        "APP-Code": "my-app-code"
      }
    }
  }
}
```

**布尔值**:
```bash
export NANOBOT_TOOLS__RESTRICT_TO_WORKSPACE="true"
export NANOBOT_CHANNELS__TELEGRAM__ENABLED="false"
```

**数组（allowFrom）**:
```bash
export NANOBOT_CHANNELS__TELEGRAM__ALLOW_FROM='["123456789","987654321"]'
```

**完整示例（.env 文件）**:
```bash
# LLM Provider
NANOBOT_PROVIDERS__ANTHROPIC__API_KEY=sk-ant-api03-xxx
NANOBOT_AGENTS__DEFAULTS__MODEL=claude-opus-4-5

# Telegram
NANOBOT_CHANNELS__TELEGRAM__ENABLED=true
NANOBOT_CHANNELS__TELEGRAM__TOKEN=YOUR_BOT_TOKEN_HERE
NANOBOT_CHANNELS__TELEGRAM__ALLOW_FROM='["123456789"]'

# Security
NANOBOT_TOOLS__RESTRICT_TO_WORKSPACE=true

# Gateway
NANOBOT_GATEWAY__HOST=0.0.0.0
NANOBOT_GATEWAY__PORT=8080
```

**代码定义位置**:
- `nanobot/config/schema.py:367` - `env_prefix="NANOBOT_"`
- `nanobot/config/schema.py:367` - `env_nested_delimiter="__"`

---

### 附录 C: 安全最佳实践

#### 1. API Key 管理

✅ **推荐做法**:
- 使用环境变量存储 API Key
- 使用密钥管理服务（AWS Secrets Manager, HashiCorp Vault）
- 定期轮换 API Key
- 为不同环境使用不同的 Key

❌ **禁止做法**:
- 将 API Key 提交到 Git 仓库
- 在日志中打印 API Key
- 在配置文件注释中保留示例 Key
- 多环境共用同一 Key

#### 2. 渠道权限控制

✅ **生产环境必备**:
```json
{
  "channels": {
    "telegram": {
      "allowFrom": ["123456789"]  // 严格白名单
    },
    "slack": {
      "groupPolicy": "allowlist",
      "groupAllowFrom": ["C01234ABCDE"],
      "dm": {
        "policy": "allowlist",
        "allowFrom": ["U01234ABCDE"]
      }
    }
  }
}
```

#### 3. 工具沙箱化

✅ **企业部署强制启用**:
```json
{
  "agents": {
    "defaults": {
      "workspace": "/opt/nanobot/workspace"
    }
  },
  "tools": {
    "restrictToWorkspace": true
  }
}
```

✅ **额外隔离措施**:
- 使用 Docker 容器运行 nanobot
- 使用专用用户运行服务（非 root）
- 限制文件系统访问权限（chmod, chown）

#### 4. 网络隔离

✅ **内网部署**:
```json
{
  "gateway": {
    "host": "127.0.0.1",  // 仅本地访问
    "port": 18790
  }
}
```

✅ **反向代理（Nginx）**:
```nginx
server {
    listen 443 ssl;
    server_name bot.company.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:18790;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

#### 5. 日志审计

✅ **记录关键事件**:
- 用户身份（sender_id, chat_id）
- 消息内容（合规前提下）
- 工具调用记录
- 错误和异常

✅ **日志安全**:
- 脱敏敏感信息（API Key, 密码）
- 使用结构化日志（JSON）
- 集中存储和分析（ELK, Splunk）

#### 6. 依赖安全

✅ **定期更新**:
```bash
uv pip list --outdated
uv pip install --upgrade nanobot
```

✅ **漏洞扫描**:
```bash
pip-audit
```

#### 7. 配置文件权限

✅ **限制访问**:
```bash
chmod 600 ~/.nanobot/config.json
chown nanobot:nanobot ~/.nanobot/config.json
```

#### 8. 生产环境检查清单

- [ ] 所有 API Key 使用环境变量
- [ ] 所有渠道配置 `allowFrom` 白名单
- [ ] 启用 `tools.restrictToWorkspace`
- [ ] Gateway `host` 设置为 `127.0.0.1` 或使用反向代理
- [ ] 使用非 root 用户运行服务
- [ ] 启用 HTTPS（通过反向代理）
- [ ] 配置文件权限设置为 600
- [ ] 日志脱敏并集中存储
- [ ] 定期审查白名单和权限
- [ ] 监控异常调用和错误

---

### 附录 D: 字段速查索引

**按字母序排列，带直接跳转链接**

#### A
- [`agents.defaults.maxTokens`](#maxtokens)
- [`agents.defaults.maxToolIterations`](#maxtooliterations)
- [`agents.defaults.memoryWindow`](#memorywindow)
- [`agents.defaults.model`](#model)
- [`agents.defaults.temperature`](#temperature)
- [`agents.defaults.workspace`](#workspace)

#### C
- [`channels.sendProgress`](#sendprogress)
- [`channels.sendToolHints`](#sendtoolhints)
- [`channels.telegram.enabled`](#431-telegram)
- [`channels.telegram.token`](#431-telegram)
- [`channels.telegram.allowFrom`](#431-telegram)
- [`channels.telegram.proxy`](#431-telegram)
- [`channels.telegram.replyToMessage`](#431-telegram)
- [`channels.discord.*`](#432-discord)
- [`channels.slack.*`](#433-slack)
- [`channels.email.*`](#434-email)

#### G
- [`gateway.host`](#host)
- [`gateway.port`](#port)
- [`gateway.heartbeat.enabled`](#heartbeatenabled)
- [`gateway.heartbeat.intervalS`](#heartbeatintervals)

#### P
- [`providers.*.apiKey`](#apikey)
- [`providers.*.apiBase`](#apibase)
- [`providers.*.extraHeaders`](#extraheaders)
- [`providers.anthropic`](#anthropic)
- [`providers.openai`](#openai)
- [`providers.deepseek`](#deepseek)
- [`providers.openrouter`](#openrouter)

#### T
- [`tools.web.search.apiKey`](#51-web-搜索工具)
- [`tools.web.search.maxResults`](#51-web-搜索工具)
- [`tools.exec.timeout`](#52-shell-执行工具)
- [`tools.restrictToWorkspace`](#53-工作空间沙箱)
- [`tools.mcpServers`](#54-mcp-外部工具)

---

**文档版本**: v1.0
**最后更新**: 2026-03-19
**维护者**: Nanobot 团队

如有问题或建议，请访问: https://github.com/your-repo/nanobot/issues

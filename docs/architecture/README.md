# Nanobot 架构文档

欢迎查阅 nanobot 的架构文档。本文档体系旨在帮助开发者深入理解 nanobot 的设计理念、核心组件和扩展机制。

## 📚 文档导航

### 总体架构
- **[00-overview.md](./00-overview.md)** - 系统架构总览、设计理念和核心概念

### 核心组件 (01-core-components/)
1. **[agent-loop.md](./01-core-components/agent-loop.md)** - Agent 核心消息处理循环
2. **[message-bus.md](./01-core-components/message-bus.md)** - 异步消息总线系统
3. **[provider-system.md](./01-core-components/provider-system.md)** - 多 LLM 提供商抽象层
4. **[channel-system.md](./01-core-components/channel-system.md)** - 多平台聊天接口系统

### 高级特性 (02-advanced-features/)
1. **[subagent-system.md](./02-advanced-features/subagent-system.md)** - 后台子任务执行机制
2. **[memory-consolidation.md](./02-advanced-features/memory-consolidation.md)** - 双层记忆整理系统
3. **[skills-loading.md](./02-advanced-features/skills-loading.md)** - 三级技能加载策略
4. **[session-management.md](./02-advanced-features/session-management.md)** - 会话持久化与管理

### 基础设施 (03-infrastructure/)
1. **[heartbeat-service.md](./03-infrastructure/heartbeat-service.md)** - 定期唤醒服务
2. **[cron-scheduling.md](./03-infrastructure/cron-scheduling.md)** - 定时任务调度系统
3. **[context-building.md](./03-infrastructure/context-building.md)** - 上下文构建机制

### 扩展开发指南 (04-extension-guide/)
1. **[adding-channels.md](./04-extension-guide/adding-channels.md)** - 如何添加新的聊天平台
2. **[adding-tools.md](./04-extension-guide/adding-tools.md)** - 如何开发自定义工具
3. **[adding-skills.md](./04-extension-guide/adding-skills.md)** - 如何创建新技能
4. **[adding-providers.md](./04-extension-guide/adding-providers.md)** - 如何集成新 LLM 提供商

### 参考文档 (05-reference/)
1. **[file-index.md](./05-reference/file-index.md)** - 完整文件路径索引
2. **[data-flow-diagrams.md](./05-reference/data-flow-diagrams.md)** - 数据流可视化图表
3. **[class-diagrams.md](./05-reference/class-diagrams.md)** - 类图与依赖关系

## 🎯 快速开始

- **新手**: 从 [00-overview.md](./00-overview.md) 开始，了解 nanobot 的整体架构
- **开发者**: 查阅 [核心组件](./01-core-components/) 理解各模块实现
- **扩展者**: 参考 [扩展开发指南](./04-extension-guide/) 添加新功能
- **维护者**: 使用 [参考文档](./05-reference/) 快速定位代码位置

## 📊 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                    Gateway (CLI Command)                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ asyncio.gather(                                       │  │
│  │   agent.run(),         # 消息处理循环                │  │
│  │   channels.start_all(), # 所有 Channel 监听器        │  │
│  │   cron.start(),        # 定时任务调度器              │  │
│  │   heartbeat.start()    # 定期唤醒服务                │  │
│  │ )                                                     │  │
│  └──────────────────────────────────────────────────────┘  │
└───────────┬─────────────────────────────────────────────────┘
            │
    ┌───────┴────────┬──────────────┬───────────────┐
    │                │              │               │
    ▼                ▼              ▼               ▼
┌─────────┐   ┌──────────────┐  ┌────────┐   ┌──────────┐
│MessageBus│   │  AgentLoop   │  │Channels│   │  Cron    │
│         │   │              │  │Manager │   │  Service │
│inbound  │   │• provider    │  │        │   │          │
│outbound │   │• tools       │  │• 9平台 │   │• 3种模式 │
│         │   │• context     │  │• 统一  │   │• 弹性    │
│         │   │• sessions    │  │  接口  │   │  定时器  │
│         │   │• subagents   │  │        │   │          │
└─────────┘   └──────────────┘  └────────┘   └──────────┘
```

## 🏗️ 核心设计模式

| 模式 | 应用 | 优势 |
|------|------|------|
| **事件驱动** | MessageBus 双队列 | 解耦、异步、背压控制 |
| **插件架构** | BaseChannel 抽象 | 易扩展、统一接口 |
| **注册表模式** | ProviderSpec Registry | 元数据驱动、单一配置源 |
| **三级匹配** | Provider 路由 | 显式 > 关键词 > 回退 |
| **会话隔离** | Cron/Thread Session Key | 独立上下文、无污染 |
| **渐进式加载** | Skills 三级策略 | 按需加载、降低开销 |

## 📈 技术栈

- **语言**: Python 3.10+
- **异步框架**: asyncio
- **LLM 集成**: LiteLLM (17+ 提供商)
- **消息平台**: Telegram, Discord, Slack, Email, Feishu, 等
- **持久化**: JSONL (会话), Markdown (记忆)
- **配置**: Pydantic v2

## 🔍 关键特性

1. ✅ **全异步架构** - 高并发、非阻塞 I/O
2. ✅ **模块解耦** - Channel/Agent/Provider/Tools 独立
3. ✅ **智能记忆** - 双层记忆 + LLM 驱动整理
4. ✅ **多模态支持** - Vision API (base64 图片)
5. ✅ **后台任务** - Subagent 并行处理
6. ✅ **定时调度** - at/every/cron 三种模式
7. ✅ **工具热插拔** - MCP 动态注册外部工具
8. ✅ **多平台统一** - 9 个聊天平台统一接口

## 📝 适用场景

- ✅ 个人 AI 助手（多平台统一接口）
- ✅ 企业内部机器人（Slack/Feishu/DingTalk）
- ✅ 定时任务自动化（Cron 系统）
- ✅ 单机部署（零外部依赖）
- ❌ 分布式部署（进程内 MessageBus）
- ❌ 高可用集群（无分布式锁）
- ❌ HTTP API 服务（无 REST Gateway）

## 🤝 贡献

欢迎为架构文档贡献：
- 修正技术错误
- 补充代码示例
- 改进图表说明
- 更新过时内容

## 📄 License

本文档遵循 nanobot 项目的 LICENSE。

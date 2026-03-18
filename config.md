# nanobot配置文件说明
## agents defaults配置
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
```
# Typer 和 Rich 库使用指南

基于 nanobot 项目的实践经验

---

## 目录

1. [概述](#概述)
2. [Typer 使用技巧](#typer-使用技巧)
3. [Rich 使用技巧](#rich-使用技巧)
4. [Typer + Rich 组合模式](#typer--rich-组合模式)
5. [高级技巧](#高级技巧)
6. [可借鉴价值总结](#可借鉴价值总结)

---

## 概述

### 为什么选择 Typer 和 Rich？

**Typer** (v0.20.0+)
- 基于 Python 3.11+ 类型注解的现代 CLI 框架
- 自动生成帮助文档和参数验证
- 与 Click 兼容，但 API 更简洁
- 支持异步命令（通过 `asyncio.run()`）

**Rich** (v14.0.0+)
- 终端富文本渲染库
- 支持 Markdown、表格、进度条、语法高亮等
- 与 Typer 无缝集成

**在 nanobot 项目中的作用：**
- Typer：构建 `nanobot` CLI 命令行工具（`nanobot agent`, `nanobot gateway`, `nanobot cron`, etc.）
- Rich：美化终端输出，提升用户体验（表格、Markdown、着色、状态指示器）

---

## Typer 使用技巧

### 1. 基础应用结构

**文件：** `nanobot/cli/commands.py:24-28`

```python
import typer
from rich.console import Console

# 创建主应用
app = typer.Typer(
    name="nanobot",
    help=f"{__logo__} nanobot - Personal AI Assistant",
    no_args_is_help=True,  # 无参数时显示帮助
)

console = Console()  # Rich 控制台实例
```

**可借鉴价值：**
- `no_args_is_help=True`：无参数时自动显示帮助（避免空白输出）
- 将 Rich Console 实例定义为模块级全局变量，供所有命令共享

---

### 2. 命令定义：使用装饰器

**文件：** `nanobot/cli/commands.py:476-482`

```python
@app.command()
def agent(
    message: str = typer.Option(None, "--message", "-m", help="Message to send to the agent"),
    session_id: str = typer.Option("cli:direct", "--session", "-s", help="Session ID"),
    markdown: bool = typer.Option(True, "--markdown/--no-markdown", help="Render assistant output as Markdown"),
    logs: bool = typer.Option(False, "--logs/--no-logs", help="Show nanobot runtime logs during chat"),
):
    """Interact with the agent directly."""
    # 命令实现...
```

**可借鉴价值：**
- **类型注解 + 默认值**：自动生成帮助文档和参数验证
- **`typer.Option()`**：定义选项参数（`--message`, `-m` 短选项）
- **布尔开关**：`--markdown/--no-markdown` 自动生成正反开关
- **文档字符串**：自动成为命令描述（在 `--help` 中显示）

---

### 3. 子命令：命令分组

**文件：** `nanobot/cli/commands.py:648-649, 831-832`

```python
# 创建子命令组
channels_app = typer.Typer(help="Manage channels")
app.add_typer(channels_app, name="channels")

cron_app = typer.Typer(help="Manage scheduled tasks")
app.add_typer(cron_app, name="cron")

# 在子应用中定义命令
@channels_app.command("status")
def channels_status():
    """Show channel status."""
    # ...

@cron_app.command("list")
def cron_list(
    all: bool = typer.Option(False, "--all", "-a", help="Include disabled jobs"),
):
    """List scheduled jobs."""
    # ...
```

**使用方式：**
```bash
nanobot channels status
nanobot cron list --all
```

**可借鉴价值：**
- **逻辑分组**：将相关命令组织到子应用（`channels`, `cron`, `provider`）
- **命名空间隔离**：避免命令名冲突
- **模块化设计**：易于扩展新的命令组

---

### 4. 参数类型：Argument vs Option

**文件：** `nanobot/cli/commands.py:941-944, 888-899`

```python
# Argument: 位置参数（必需）
@cron_app.command("remove")
def cron_remove(
    job_id: str = typer.Argument(..., help="Job ID to remove"),
):
    """Remove a scheduled job."""
    # ...

# Option: 选项参数（可选或有默认值）
@cron_app.command("add")
def cron_add(
    name: str = typer.Option(..., "--name", "-n", help="Job name"),  # 必需选项
    message: str = typer.Option(..., "--message", "-m", help="Message for agent"),
    every: int = typer.Option(None, "--every", "-e", help="Run every N seconds"),  # 可选
    cron_expr: str = typer.Option(None, "--cron", "-c", help="Cron expression"),
):
    """Add a scheduled job."""
    # ...
```

**使用方式：**
```bash
nanobot cron remove job123                           # Argument
nanobot cron add --name daily --message "Check news" --every 3600  # Options
```

**可借鉴价值：**
- **Argument**：用于核心、必需的位置参数（如 ID、路径）
- **Option**：用于可选配置（flags、过滤器、开关）
- **`...` (Ellipsis)**：标记为必需参数（Option 默认可选）

---

### 5. 回调函数：版本显示

**文件：** `nanobot/cli/commands.py:135-148`

```python
def version_callback(value: bool):
    """当 --version 被触发时执行"""
    if value:
        console.print(f"{__logo__} nanobot v{__version__}")
        raise typer.Exit()  # 退出程序

@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version", "-v",
        callback=version_callback,
        is_eager=True,  # 优先执行（在其他命令之前）
    ),
):
    """nanobot - Personal AI Assistant."""
    pass
```

**可借鉴价值：**
- **`is_eager=True`**：在参数解析时立即执行回调（用于 `--version`, `--help` 等）
- **`typer.Exit()`**：优雅退出（不抛异常）
- **全局回调**：使用 `@app.callback()` 定义应用级选项

---

### 6. 确认提示：交互式输入

**文件：** `nanobot/cli/commands.py:169-176`

```python
if config_path.exists():
    console.print(f"[yellow]Config already exists at {config_path}[/yellow]")
    console.print("  [bold]y[/bold] = overwrite with defaults (existing values will be lost)")
    console.print("  [bold]N[/bold] = refresh config, keeping existing values and adding new fields")

    if typer.confirm("Overwrite?"):  # 布尔确认提示
        config = Config()
        save_config(config)
        console.print(f"[green]✓[/green] Config reset to defaults at {config_path}")
    else:
        config = load_config()
        save_config(config)
        console.print(f"[green]✓[/green] Config refreshed at {config_path}")
```

**可借鉴价值：**
- **`typer.confirm()`**：yes/no 确认提示（返回 `True`/`False`）
- **Rich 着色**：`[yellow]`, `[green]`, `[bold]` 增强可读性
- **提前说明后果**：告知用户每个选项的影响

---

### 7. 错误处理：优雅退出

**文件：** `nanobot/cli/commands.py:296-300, 905-907`

```python
# 示例1: 缺少 API key
if not (p and p.api_key) and not (spec and spec.is_oauth):
    console.print("[red]Error: No API key configured.[/red]")
    console.print("Set one in ~/.nanobot/config.json under providers section")
    raise typer.Exit(1)  # 退出码 1（表示错误）

# 示例2: 参数冲突
if tz and not cron_expr:
    console.print("[red]Error: --tz can only be used with --cron[/red]")
    raise typer.Exit(1)
```

**可借鉴价值：**
- **`typer.Exit(code)`**：设置退出码（0=成功，1=错误）
- **友好错误信息**：说明问题 + 解决方案
- **着色区分**：`[red]` 标记错误，`[green]` 标记成功

---

### 8. 异步命令：集成 asyncio

**文件：** `nanobot/cli/commands.py:538-545, 564-640`

```python
@app.command()
def agent(message: str = typer.Option(None, ...)):
    """Interact with the agent directly."""
    # Typer 命令必须是同步的，但可以内部调用 asyncio.run()

    if message:
        # 单次消息模式
        async def run_once():
            response = await agent_loop.process_direct(message, session_id, on_progress=_cli_progress)
            _print_agent_response(response, render_markdown=markdown)
            await agent_loop.close_mcp()

        asyncio.run(run_once())  # 运行异步函数
    else:
        # 交互式模式
        async def run_interactive():
            bus_task = asyncio.create_task(agent_loop.run())
            # ...
            while True:
                user_input = await _read_interactive_input_async()
                await bus.publish_inbound(InboundMessage(...))
                # ...

        asyncio.run(run_interactive())
```

**可借鉴价值：**
- **模式1：单次调用**：`asyncio.run(async_function())`
- **模式2：长期运行**：在 async 函数内启动多个任务
- **清理资源**：`finally` 块中关闭连接

---

## Rich 使用技巧

### 1. 基础输出：着色和格式化

**文件：** `nanobot/cli/commands.py:30, 105-106, 166`

```python
from rich.console import Console

console = Console()

# 基础着色（支持 BBCode 风格标签）
console.print("[red]Error: Something went wrong[/red]")
console.print("[green]✓[/green] Success!")
console.print("[yellow]Warning: Check your config[/yellow]")
console.print("[cyan]Info: Processing...[/cyan]")
console.print("[dim]Details: Additional context[/dim]")
console.print("[bold]Important[/bold] message")

# 组合使用
console.print(f"[green]✓[/green] Created config at {config_path}")
console.print(f"{__logo__} nanobot v{__version__}")
```

**可用颜色标签：**
- 基础颜色：`red`, `green`, `blue`, `yellow`, `magenta`, `cyan`, `white`
- ANSI 颜色：`ansiblue`, `ansired`, etc.
- 样式：`bold`, `dim`, `italic`, `underline`

**可借鉴价值：**
- **一致的视觉语言**：
  - ✓ 绿色 = 成功
  - ✗ 红色 = 错误
  - ⚠ 黄色 = 警告
  - [dim] = 次要信息
- **Unicode 符号**：✓ ✗ → 比纯文本更直观

---

### 2. Markdown 渲染

**文件：** `nanobot/cli/commands.py:12, 100-107`

```python
from rich.markdown import Markdown
from rich.text import Text

def _print_agent_response(response: str, render_markdown: bool) -> None:
    """渲染助手响应，支持 Markdown 或纯文本"""
    content = response or ""

    # 根据配置选择渲染方式
    body = Markdown(content) if render_markdown else Text(content)

    console.print()  # 空行
    console.print(f"[cyan]{__logo__} nanobot[/cyan]")
    console.print(body)  # Rich 自动处理 Markdown 或 Text 对象
    console.print()
```

**Markdown 支持的功能：**
- 标题（`#`, `##`, `###`）
- 粗体（`**text**`）、斜体（`*text*`）
- 代码块（` ```language ... ``` `）
- 列表（`-`, `1.`）
- 引用（`>`）
- 链接（`[text](url)`）

**可借鉴价值：**
- **自动排版**：Markdown 自动处理缩进、换行、代码高亮
- **可配置**：允许用户禁用 Markdown（`--no-markdown`）
- **统一输出**：LLM 响应天然是 Markdown，直接渲染

---

### 3. 表格：结构化数据展示

**文件：** `nanobot/cli/commands.py:659-742, 852-885`

```python
from rich.table import Table

@channels_app.command("status")
def channels_status():
    """Show channel status."""
    config = load_config()

    # 创建表格
    table = Table(title="Channel Status")

    # 定义列（名称 + 样式）
    table.add_column("Channel", style="cyan")
    table.add_column("Enabled", style="green")
    table.add_column("Configuration", style="yellow")

    # 添加行
    wa = config.channels.whatsapp
    table.add_row(
        "WhatsApp",
        "✓" if wa.enabled else "✗",
        wa.bridge_url
    )

    fs = config.channels.feishu
    fs_config = f"app_id: {fs.app_id[:10]}..." if fs.app_id else "[dim]not configured[/dim]"
    table.add_row("Feishu", "✓" if fs.enabled else "✗", fs_config)

    # 渲染表格
    console.print(table)
```

**输出效果：**
```
                Channel Status
┏━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
┃ Channel  ┃ Enabled ┃ Configuration        ┃
┡━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
│ WhatsApp │ ✓       │ http://localhost:... │
│ Feishu   │ ✗       │ not configured       │
└──────────┴─────────┴──────────────────────┘
```

**Cron 任务表格示例（更复杂）：**

**文件：** `nanobot/cli/commands.py:852-885`

```python
@cron_app.command("list")
def cron_list(all: bool = typer.Option(False, "--all", "-a", help="Include disabled jobs")):
    """List scheduled jobs."""
    service = CronService(store_path)
    jobs = service.list_jobs(include_disabled=all)

    if not jobs:
        console.print("No scheduled jobs.")
        return

    table = Table(title="Scheduled Jobs")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Schedule")
    table.add_column("Status")
    table.add_column("Next Run")

    for job in jobs:
        # 格式化调度表达式
        if job.schedule.kind == "every":
            sched = f"every {(job.schedule.every_ms or 0) // 1000}s"
        elif job.schedule.kind == "cron":
            sched = f"{job.schedule.expr or ''} ({job.schedule.tz})" if job.schedule.tz else (job.schedule.expr or "")
        else:
            sched = "one-time"

        # 格式化下次运行时间
        if job.state.next_run_at_ms:
            ts = job.state.next_run_at_ms / 1000
            next_run = datetime.fromtimestamp(ts, tz).strftime("%Y-%m-%d %H:%M")
        else:
            next_run = ""

        # 状态着色
        status = "[green]enabled[/green]" if job.enabled else "[dim]disabled[/dim]"

        table.add_row(job.id, job.name, sched, status, next_run)

    console.print(table)
```

**可借鉴价值：**
- **列样式**：每列独立着色（`style="cyan"`）
- **单元格着色**：行内使用 `[green]`, `[dim]` 标签
- **动态内容**：根据数据生成格式化字符串
- **空状态处理**：无数据时显示提示信息

---

### 4. 状态指示器（Spinner）

**文件：** `nanobot/cli/commands.py:522-527, 541-542, 621-622`

```python
def _thinking_ctx():
    """根据日志配置返回状态指示器或空上下文"""
    if logs:
        from contextlib import nullcontext
        return nullcontext()  # 日志开启时不显示 spinner

    # 返回 Rich 状态指示器（带动画）
    return console.status("[dim]nanobot is thinking...[/dim]", spinner="dots")

# 使用方式
async def run_once():
    with _thinking_ctx():  # 自动显示/隐藏 spinner
        response = await agent_loop.process_direct(message, session_id)
    _print_agent_response(response, render_markdown=markdown)
```

**可用 Spinner 样式：**
- `"dots"` - ⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏
- `"line"` - `-` `\\` `|` `/`
- `"arrow"` - ← ↖ ↑ ↗ → ↘ ↓ ↙

**可借鉴价值：**
- **条件渲染**：日志开启时禁用 spinner（避免输出混乱）
- **上下文管理器**：自动启动/停止动画
- **用户体验**：长时间操作时提供视觉反馈

---

### 5. 进度信息：实时更新

**文件：** `nanobot/cli/commands.py:529-535, 574-582`

```python
async def _cli_progress(content: str, *, tool_hint: bool = False) -> None:
    """显示 agent 进度（工具调用提示）"""
    ch = agent_loop.channels_config

    # 根据配置过滤输出
    if ch and tool_hint and not ch.send_tool_hints:
        return
    if ch and not tool_hint and not ch.send_progress:
        return

    # 显示为次要信息（灰色、缩进）
    console.print(f"  [dim]↳ {content}[/dim]")

# 在 agent loop 中使用
response = await agent_loop.process_direct(
    message,
    session_id,
    on_progress=_cli_progress  # 传递回调
)
```

**输出效果：**
```
  ↳ web_search("latest AI news")
  ↳ read_file("config.json")
  ↳ Analyzing results...
```

**可借鉴价值：**
- **回调模式**：Agent 通过回调报告进度
- **可配置性**：用户可禁用工具提示（`send_tool_hints=False`）
- **视觉层次**：缩进 + `[dim]` + 箭头符号

---

## Typer + Rich 组合模式

### 1. 统一的终端输出风格

**文件：** `nanobot/cli/commands.py:30, 192-196`

```python
# 模块级共享 Console 实例
console = Console()

# 所有命令使用相同的输出方式
@app.command()
def onboard():
    console.print(f"\n{__logo__} nanobot is ready!")
    console.print("\nNext steps:")
    console.print("  1. Add your API key to [cyan]~/.nanobot/config.json[/cyan]")
    console.print("     Get one at: https://openrouter.ai/keys")
    console.print("  2. Chat: [cyan]nanobot agent -m \"Hello!\"[/cyan]")
    console.print("\n[dim]Want Telegram/WhatsApp? See: https://github.com/HKUDS/nanobot#-chat-apps[/dim]")
```

**可借鉴价值：**
- **一致性**：所有命令使用同一个 Console 实例
- **品牌化**：统一使用 `{__logo__}` 符号
- **链接高亮**：URL 使用 `[cyan]` 着色
- **层级信息**：主要信息 + 次要提示（`[dim]`）

---

### 2. 错误处理 + 友好提示

**文件：** `nanobot/cli/commands.py:773-798`

```python
# 检查依赖
if not shutil.which("npm"):
    console.print("[red]npm not found. Please install Node.js >= 18.[/red]")
    raise typer.Exit(1)

# 捕获子进程错误
try:
    subprocess.run(["npm", "install"], cwd=user_bridge, check=True, capture_output=True)
    subprocess.run(["npm", "run", "build"], cwd=user_bridge, check=True, capture_output=True)
    console.print("[green]✓[/green] Bridge ready\n")
except subprocess.CalledProcessError as e:
    console.print(f"[red]Build failed: {e}[/red]")
    if e.stderr:
        console.print(f"[dim]{e.stderr.decode()[:500]}[/dim]")  # 截断错误输出
    raise typer.Exit(1)
```

**可借鉴价值：**
- **前置检查**：依赖检查 + 清晰的错误消息
- **错误截断**：只显示前 500 字符（避免淹没终端）
- **分层信息**：错误摘要（红色）+ 详细日志（灰色）

---

### 3. 交互式确认 + 状态反馈

**文件：** `nanobot/cli/commands.py:169-176, 777-793`

```python
# 确认 + 视觉反馈
if typer.confirm("Overwrite?"):
    config = Config()
    save_config(config)
    console.print(f"[green]✓[/green] Config reset to defaults at {config_path}")
else:
    config = load_config()
    save_config(config)
    console.print(f"[green]✓[/green] Config refreshed at {config_path}")

# 多步骤操作 + 进度提示
console.print(f"{__logo__} Setting up bridge...")
console.print("  Installing dependencies...")
subprocess.run(["npm", "install"], cwd=user_bridge, check=True, capture_output=True)
console.print("  Building...")
subprocess.run(["npm", "run", "build"], cwd=user_bridge, check=True, capture_output=True)
console.print("[green]✓[/green] Bridge ready\n")
```

**可借鉴价值：**
- **步骤提示**：告知用户当前进度
- **静默输出**：`capture_output=True` 避免混乱
- **完成确认**：显示绿色 ✓ 标记

---

## 高级技巧

### 1. 异步交互式 CLI：prompt_toolkit 集成

**文件：** `nanobot/cli/commands.py:17-19, 79-98, 115-132`

```python
from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout

_PROMPT_SESSION: PromptSession | None = None

def _init_prompt_session() -> None:
    """创建带持久历史的 prompt_toolkit 会话"""
    global _PROMPT_SESSION

    history_file = Path.home() / ".nanobot" / "history" / "cli_history"
    history_file.parent.mkdir(parents=True, exist_ok=True)

    _PROMPT_SESSION = PromptSession(
        history=FileHistory(str(history_file)),  # 持久化命令历史
        enable_open_in_editor=False,
        multiline=False,  # Enter 提交（单行模式）
    )

async def _read_interactive_input_async() -> str:
    """异步读取用户输入"""
    if _PROMPT_SESSION is None:
        raise RuntimeError("Call _init_prompt_session() first")

    try:
        with patch_stdout():  # 防止 Rich 输出干扰 prompt_toolkit
            return await _PROMPT_SESSION.prompt_async(
                HTML("<b fg='ansiblue'>You:</b> "),  # HTML 格式化提示符
            )
    except EOFError as exc:
        raise KeyboardInterrupt from exc
```

**为什么使用 prompt_toolkit？**
- **原生支持历史记录**：上下箭头浏览历史
- **括号粘贴模式**：多行粘贴不触发立即执行
- **异步友好**：`prompt_async()` 不阻塞 asyncio 事件循环
- **清洁显示**：避免幽灵字符（ghost characters）

**可借鉴价值：**
- **混合使用**：Rich 用于输出，prompt_toolkit 用于输入
- **`patch_stdout()`**：确保 Rich 输出不破坏 prompt_toolkit 光标位置
- **持久化历史**：保存到 `~/.nanobot/history/cli_history`

---

### 2. 终端状态管理：避免输入缓冲问题

**文件：** `nanobot/cli/commands.py:38-77`

```python
_SAVED_TERM_ATTRS = None  # 原始终端设置

def _flush_pending_tty_input() -> None:
    """清除 LLM 生成期间输入的按键（避免意外输入）"""
    try:
        fd = sys.stdin.fileno()
        if not os.isatty(fd):
            return
    except Exception:
        return

    try:
        import termios
        termios.tcflush(fd, termios.TCIFLUSH)  # 清空输入缓冲区
        return
    except Exception:
        pass

    # 回退方案：手动读取并丢弃
    try:
        import select
        while True:
            ready, _, _ = select.select([fd], [], [], 0)
            if not ready:
                break
            if not os.read(fd, 4096):
                break
    except Exception:
        return

def _restore_terminal() -> None:
    """恢复终端原始状态（回显、行缓冲等）"""
    if _SAVED_TERM_ATTRS is None:
        return
    try:
        import termios
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _SAVED_TERM_ATTRS)
    except Exception:
        pass
```

**问题场景：**
用户在 LLM 思考期间敲击键盘，输入会积累在缓冲区，导致响应后立即执行意外命令。

**解决方案：**
1. **保存终端状态**：启动时记录 `termios` 属性
2. **清空缓冲区**：每轮对话前调用 `_flush_pending_tty_input()`
3. **恢复状态**：退出时调用 `_restore_terminal()`

**使用位置：**
```python
# 交互式循环中
while True:
    _flush_pending_tty_input()  # 清空缓冲区
    user_input = await _read_interactive_input_async()
    # ...

# 信号处理器中
def _exit_on_sigint(signum, frame):
    _restore_terminal()  # 恢复终端
    console.print("\nGoodbye!")
    os._exit(0)
```

**可借鉴价值：**
- **跨平台兼容**：优先 `termios`（Linux/macOS），回退到 `select`（通用）
- **优雅退出**：Ctrl+C 时恢复终端状态
- **解决痛点**：避免交互式 CLI 的常见 bug

---

### 3. 信号处理：优雅退出

**文件：** `nanobot/cli/commands.py:557-562, 626-633`

```python
import signal

def _exit_on_sigint(signum, frame):
    """Ctrl+C 信号处理器"""
    _restore_terminal()  # 恢复终端
    console.print("\nGoodbye!")
    os._exit(0)  # 强制退出（避免清理延迟）

signal.signal(signal.SIGINT, _exit_on_sigint)

# 在 asyncio 事件循环中也捕获
try:
    while True:
        user_input = await _read_interactive_input_async()
        # ...
except KeyboardInterrupt:
    _restore_terminal()
    console.print("\nGoodbye!")
    break
```

**可借鉴价值：**
- **双重捕获**：信号处理器 + try-except（覆盖所有场景）
- **清理资源**：退出前恢复终端状态
- **`os._exit()`**：跳过 Python 清理（适用于信号处理器）

---

### 4. 条件渲染：根据环境调整输出

**文件：** `nanobot/cli/commands.py:499-527`

```python
@app.command()
def agent(
    logs: bool = typer.Option(False, "--logs/--no-logs", help="Show runtime logs"),
):
    # 根据配置启用/禁用日志
    if logs:
        logger.enable("nanobot")
    else:
        logger.disable("nanobot")

    # 日志开启时不显示 spinner（避免输出冲突）
    def _thinking_ctx():
        if logs:
            from contextlib import nullcontext
            return nullcontext()
        return console.status("[dim]nanobot is thinking...[/dim]", spinner="dots")

    with _thinking_ctx():
        response = await agent_loop.process_direct(message, session_id)
```

**可借鉴价值：**
- **互斥输出**：日志 vs Spinner（二选一）
- **`nullcontext()`**：空上下文管理器（do nothing）
- **用户选择**：提供 `--logs` 开关

---

## 可借鉴价值总结

### Typer 核心模式

| 模式 | 使用场景 | 示例 |
|------|----------|------|
| **子命令分组** | 逻辑相关的命令（channels, cron, provider） | `app.add_typer(channels_app, name="channels")` |
| **Argument vs Option** | 核心参数用 Argument，配置用 Option | `typer.Argument(...)` vs `typer.Option(...)` |
| **布尔开关** | 启用/禁用功能 | `--markdown/--no-markdown` |
| **`is_eager=True`** | 优先级高的选项（--version, --help） | `callback=version_callback, is_eager=True` |
| **`typer.Exit(code)`** | 优雅退出 + 设置退出码 | `raise typer.Exit(1)` |
| **异步集成** | 长期运行或 I/O 密集任务 | `asyncio.run(async_function())` |

### Rich 核心模式

| 功能 | 使用场景 | 关键 API |
|------|----------|----------|
| **着色** | 状态指示（成功/失败/警告） | `[green]`, `[red]`, `[yellow]`, `[dim]` |
| **Markdown** | 渲染 LLM 响应 | `Markdown(content)` |
| **Table** | 列出配置、任务、状态 | `Table(title="...")`, `table.add_row(...)` |
| **Spinner** | 长时间操作反馈 | `console.status("...", spinner="dots")` |
| **Progress** | 实时进度（工具调用） | `console.print(f"[dim]↳ {content}[/dim]")` |

### 高级组合技巧

1. **Rich (输出) + prompt_toolkit (输入)**
   - 避免输出干扰输入光标
   - `patch_stdout()` 确保兼容性

2. **终端状态管理**
   - 保存/恢复 `termios` 属性
   - 清空输入缓冲区（`tcflush`）

3. **条件渲染**
   - 根据 `--logs` 开关调整输出
   - 日志 vs Spinner 互斥

4. **信号处理**
   - 捕获 Ctrl+C
   - 优雅清理资源

---

## 实践建议

### 1. 项目结构

```
project/
├── cli/
│   ├── __init__.py
│   └── commands.py      # 主命令文件
├── config/
│   └── schema.py        # 配置数据类
└── main.py
```

### 2. 依赖声明（pyproject.toml）

```toml
dependencies = [
    "typer>=0.20.0,<1.0.0",
    "rich>=14.0.0,<15.0.0",
    "prompt-toolkit>=3.0.50,<4.0.0",  # 可选：交互式 CLI
]

[project.scripts]
myapp = "myapp.cli.commands:app"
```

### 3. 最小可运行示例

```python
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="My CLI Tool")
console = Console()

@app.command()
def hello(
    name: str = typer.Option(..., "--name", "-n", help="Your name"),
    color: bool = typer.Option(True, "--color/--no-color"),
):
    """Say hello."""
    if color:
        console.print(f"[green]Hello, {name}![/green]")
    else:
        print(f"Hello, {name}!")

@app.command()
def status():
    """Show status."""
    table = Table(title="System Status")
    table.add_column("Service", style="cyan")
    table.add_column("Status", style="green")
    table.add_row("Database", "✓ Running")
    table.add_row("API", "✗ Down")
    console.print(table)

if __name__ == "__main__":
    app()
```

**运行：**
```bash
python myapp.py hello --name Alice
python myapp.py status
python myapp.py --help
```

---

## 参考资源

- **Typer 官方文档**：https://typer.tiangolo.com/
- **Rich 官方文档**：https://rich.readthedocs.io/
- **nanobot 项目**：https://github.com/HKUDS/nanobot
- **prompt_toolkit 文档**：https://python-prompt-toolkit.readthedocs.io/

---

## 总结

**Typer 的核心价值：**
- 类型注解驱动（自动生成帮助、验证参数）
- 子命令分组（模块化设计）
- 与 asyncio 无缝集成

**Rich 的核心价值：**
- 终端富文本（着色、表格、Markdown）
- 提升用户体验（Spinner、进度提示）
- 与 Typer 完美配合

**组合使用的最佳实践：**
1. 模块级共享 `Console()` 实例
2. 统一的视觉语言（颜色、符号）
3. 条件渲染（根据 `--logs` 调整输出）
4. 混合 prompt_toolkit（交互式输入）
5. 终端状态管理（避免缓冲区问题）

通过学习 nanobot 的实现，可以快速掌握现代 Python CLI 开发的最佳实践。

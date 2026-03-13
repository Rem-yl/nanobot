"""
Interactive Task Manager CLI
演示 Typer + Pydantic + Rich + prompt_toolkit 的协同使用
"""
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional
import json

import typer
from pydantic import BaseModel, Field, field_validator
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from prompt_toolkit import prompt
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.validation import Validator, ValidationError

# ============ Pydantic Models (数据验证) ============
class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class Task(BaseModel):
    """任务模型 - Pydantic 提供自动验证"""
    id: int
    title: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    priority: Priority = Priority.MEDIUM
    completed: bool = False
    created_at: datetime = Field(default_factory=datetime.now)

    @field_validator('title')
    @classmethod
    def title_must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('标题不能为空')
        return v.strip()

class TaskDatabase(BaseModel):
    """任务数据库"""
    tasks: List[Task] = []
    next_id: int = 1

    def add_task(self, title: str, description: str = None,
                priority: Priority = Priority.MEDIUM) -> Task:
        task = Task(
            id=self.next_id,
            title=title,
            description=description,
            priority=priority
        )
        self.tasks.append(task)
        self.next_id += 1
        return task

    def get_task(self, task_id: int) -> Optional[Task]:
        return next((t for t in self.tasks if t.id == task_id), None)

    def save(self, file_path: Path):
        file_path.write_text(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, file_path: Path) -> 'TaskDatabase':
        if file_path.exists():
            return cls.model_validate_json(file_path.read_text())
        return cls()

# ============ Rich Console (美化输出) ============
console = Console()

def display_tasks(db: TaskDatabase):
    """使用 Rich 表格展示任务"""
    if not db.tasks:
        console.print("[yellow]暂无任务[/yellow]")
        return

    table = Table(title="📋 任务列表", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("标题", style="white")
    table.add_column("优先级", justify="center")
    table.add_column("状态", justify="center")
    table.add_column("创建时间", style="dim")

    for task in db.tasks:
        priority_colors = {
            Priority.LOW: "green",
            Priority.MEDIUM: "yellow",
            Priority.HIGH: "red"
        }
        status = "✅" if task.completed else "⏳"
        priority_text = f"[{priority_colors[task.priority]}]{task.priority.value.upper()}[/]"

        table.add_row(
            str(task.id),
            task.title,
            priority_text,
            status,
            task.created_at.strftime("%Y-%m-%d %H:%M")
        )

    console.print(table)

def display_task_detail(task: Task):
    """展示任务详情"""
    content = f"""
[bold]标题:[/bold] {task.title}
[bold]描述:[/bold] {task.description or '无'}
[bold]优先级:[/bold] {task.priority.value.upper()}
[bold]状态:[/bold] {'已完成 ✅' if task.completed else '进行中 ⏳'}
[bold]创建时间:[/bold] {task.created_at.strftime("%Y-%m-%d %H:%M:%S")}
    """.strip()

    console.print(Panel(content, title=f"任务 #{task.id}", border_style="blue"))

# ============ prompt_toolkit Validators ============
class TaskIdValidator(Validator):
    """验证任务 ID 是否存在"""
    def __init__(self, db: TaskDatabase):
        self.db = db

    def validate(self, document):
        text = document.text
        if not text.isdigit():
            raise ValidationError(message="请输入有效的数字 ID")

        task_id = int(text)
        if not self.db.get_task(task_id):
            raise ValidationError(message=f"任务 #{task_id} 不存在")

# ============ Typer CLI (命令定义) ============
app = typer.Typer(help="📝 交互式任务管理器")
DB_FILE = Path("tasks.json")

def get_db() -> TaskDatabase:
    return TaskDatabase.load(DB_FILE)

@app.command()
def list():
    """列出所有任务"""
    db = get_db()
    display_tasks(db)

@app.command()
def add():
    """交互式添加任务 (使用 prompt_toolkit)"""
    db = get_db()

    # 使用 prompt_toolkit 获取输入
    console.print("[bold cyan]创建新任务[/bold cyan]")

    title = prompt("标题: ")
    description = prompt("描述 (可选): ")

    # 优先级自动补全
    priority_completer = WordCompleter(['low', 'medium', 'high'])
    priority_input = prompt(
        "优先级 (low/medium/high): ",
        completer=priority_completer,
        default="medium"
    )

    try:
        task = db.add_task(
            title=title,
            description=description if description else None,
            priority=Priority(priority_input.lower())
        )
        db.save(DB_FILE)

        console.print(f"[green]✓ 成功创建任务 #{task.id}[/green]")
        display_task_detail(task)
    except ValueError as e:
        console.print(f"[red]✗ 错误: {e}[/red]")

@app.command()
def show(task_id: int = typer.Argument(..., help="任务 ID")):
    """显示任务详情"""
    db = get_db()
    task = db.get_task(task_id)

    if not task:
        console.print(f"[red]任务 #{task_id} 不存在[/red]")
        raise typer.Exit(code=1)

    display_task_detail(task)

@app.command()
def complete():
    """标记任务为完成 (交互式选择)"""
    db = get_db()

    if not db.tasks:
        console.print("[yellow]暂无任务[/yellow]")
        return

    display_tasks(db)

    # 使用验证器确保 ID 有效
    task_id_str = prompt(
        "输入要完成的任务 ID: ",
        validator=TaskIdValidator(db)
    )

    task_id = int(task_id_str)
    task = db.get_task(task_id)
    task.completed = True
    db.save(DB_FILE)

    console.print(f"[green]✓ 任务 #{task_id} 已标记为完成[/green]")

@app.command()
def clear():
    """清除所有任务"""
    confirm = prompt("确认删除所有任务? (yes/no): ")
    if confirm.lower() == 'yes':
        DB_FILE.unlink(missing_ok=True)
        console.print("[green]✓ 所有任务已清除[/green]")
    else:
        console.print("[yellow]已取消[/yellow]")

if __name__ == "__main__":
    app()
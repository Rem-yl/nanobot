# CronService 深度源码解析

## 目录
1. [数据结构设计](#数据结构设计)
2. [核心算法：时间计算](#核心算法时间计算)
3. [事件驱动机制](#事件驱动机制)
4. [持久化设计](#持久化设计)
5. [生命周期管理](#生命周期管理)
6. [错误处理策略](#错误处理策略)
7. [集成机制](#集成机制)
8. [实战示例](#实战示例)

---

## 数据结构设计

### 1. CronSchedule - 调度规则的抽象

```python
@dataclass
class CronSchedule:
    kind: Literal["at", "every", "cron"]  # 三种调度模式
    at_ms: int | None = None              # "at"模式：时间戳（毫秒）
    every_ms: int | None = None           # "every"模式：间隔（毫秒）
    expr: str | None = None               # "cron"模式：表达式
    tz: str | None = None                 # "cron"模式：时区
```

**设计亮点**：
- **联合类型模式**：一个类支持三种不同的调度语义
- **可选字段**：根据 `kind` 值，只有对应字段有效
- **时间单位统一**：内部全部使用毫秒（ms），避免精度损失

**三种模式对比**：

| 模式 | 使用场景 | 必需字段 | 计算逻辑 |
|------|---------|---------|---------|
| `at` | 一次性提醒 | `at_ms` | 比较时间戳 |
| `every` | 固定间隔循环 | `every_ms` | `now + interval` |
| `cron` | 复杂定时规则 | `expr`, `tz` (可选) | croniter 解析 |

### 2. CronJobState - 运行时状态跟踪

```python
@dataclass
class CronJobState:
    next_run_at_ms: int | None = None     # 下次运行时间（关键！）
    last_run_at_ms: int | None = None     # 上次运行时间
    last_status: Literal["ok", "error", "skipped"] | None = None
    last_error: str | None = None
```

**设计思想**：
- `next_run_at_ms` 是调度系统的**索引键**
- 状态与任务定义分离（`CronJob` 包含 `state`）
- 记录执行历史，支持失败追踪

**状态转换流程**：
```
[任务创建] → next_run_at_ms = _compute_next_run()
    ↓
[定时器触发] → 执行任务
    ↓
[执行成功] → last_status = "ok", last_run_at_ms = now
    ↓
[重新计算] → next_run_at_ms = _compute_next_run()
```

### 3. CronJob - 完整的任务定义

```python
@dataclass
class CronJob:
    id: str                          # 8位UUID，唯一标识
    name: str                        # 用户可读名称
    enabled: bool = True             # 启用/禁用开关
    schedule: CronSchedule           # 调度规则（组合模式）
    payload: CronPayload             # 执行载荷（要做什么）
    state: CronJobState              # 运行时状态（组合模式）
    created_at_ms: int = 0
    updated_at_ms: int = 0
    delete_after_run: bool = False   # 一次性任务标记
```

**关键设计模式**：
- **组合模式**：`schedule` + `payload` + `state` 分离关注点
- **不可变 ID**：创建时生成，8字符足够防碰撞（生日悖论）
- **软删除支持**：通过 `enabled` 字段而非物理删除

---

## 核心算法：时间计算

### _compute_next_run() - 调度算法的核心

```python
def _compute_next_run(schedule: CronSchedule, now_ms: int) -> int | None:
    if schedule.kind == "at":
        # 一次性执行：检查是否已过期
        return schedule.at_ms if schedule.at_ms and schedule.at_ms > now_ms else None

    if schedule.kind == "every":
        # 固定间隔：简单加法
        if not schedule.every_ms or schedule.every_ms <= 0:
            return None
        return now_ms + schedule.every_ms

    if schedule.kind == "cron" and schedule.expr:
        try:
            from croniter import croniter
            from zoneinfo import ZoneInfo

            # 关键步骤1：确定时区
            base_time = now_ms / 1000  # 转换为秒
            tz = ZoneInfo(schedule.tz) if schedule.tz else datetime.now().astimezone().tzinfo

            # 关键步骤2：创建时区感知的 datetime
            base_dt = datetime.fromtimestamp(base_time, tz=tz)

            # 关键步骤3：使用 croniter 计算下次运行
            cron = croniter(schedule.expr, base_dt)
            next_dt = cron.get_next(datetime)

            # 关键步骤4：转回毫秒时间戳（UTC）
            return int(next_dt.timestamp() * 1000)
        except Exception:
            return None  # 容错：表达式无效则任务不可调度

    return None
```

**算法分析**：

#### 1. "at" 模式 - O(1) 简单比较
```python
# 示例：在 2026-03-15 10:00:00 执行一次
at_ms = 1741946400000  # 预先计算好的时间戳

# 计算逻辑
if at_ms > now_ms:
    return at_ms  # 未到期
else:
    return None   # 已过期，任务不再运行
```

#### 2. "every" 模式 - O(1) 线性增长
```python
# 示例：每5秒执行一次
every_ms = 5000

# 第1次：now = 1000 → next = 6000
# 第2次：now = 6000 → next = 11000
# 第3次：now = 11000 → next = 16000
# ...

# 计算逻辑（无状态，每次从当前时间起算）
return now_ms + every_ms
```

**注意陷阱**：如果任务执行耗时 > every_ms，会导致任务积压！
```python
# 假设 every_ms = 5000，但任务执行需要 8 秒
# t=0s:   任务1开始
# t=5s:   计算next=10s（但任务1还在运行）
# t=8s:   任务1结束，已经超过5s
# t=10s:  任务2开始（实际间隔15s，不是5s！）
```

#### 3. "cron" 模式 - 依赖 croniter 库

**Cron 表达式格式**：
```
┌───────────── 分钟 (0 - 59)
│ ┌───────────── 小时 (0 - 23)
│ │ ┌───────────── 日期 (1 - 31)
│ │ │ ┌───────────── 月份 (1 - 12)
│ │ │ │ ┌───────────── 星期 (0 - 6) (0=周日)
│ │ │ │ │
* * * * *
```

**示例**：
```python
# 每天 9:00 AM
"0 9 * * *"

# 每周一 10:30 AM
"30 10 * * 1"

# 每月1号和15号 14:00
"0 14 1,15 * *"
```

**时区处理的关键**：
```python
# 错误理解：以为时间戳是本地时间
base_dt = datetime.fromtimestamp(base_time)  # ❌ 使用系统默认时区

# 正确做法：明确指定时区
tz = ZoneInfo("America/Vancouver")
base_dt = datetime.fromtimestamp(base_time, tz=tz)  # ✓ 时区感知

# 示例：同一个表达式在不同时区的差异
expr = "0 9 * * *"  # 每天9点

# Vancouver时间（UTC-8/-7）
tz_van = ZoneInfo("America/Vancouver")
# 当 Vancouver 本地时间为 2026-03-15 09:00:00 时
# UTC 时间为 2026-03-15 17:00:00 (假设 DST 生效)

# Shanghai时间（UTC+8）
tz_sha = ZoneInfo("Asia/Shanghai")
# 当 Shanghai 本地时间为 2026-03-15 09:00:00 时
# UTC 时间为 2026-03-15 01:00:00

# 两个任务的实际执行相差 16 小时！
```

---

## 事件驱动机制

### 传统轮询 vs 事件驱动对比

#### ❌ 传统轮询方式（低效）
```python
async def polling_scheduler():
    while True:
        now = time.time()
        for job in jobs:
            if job.next_run <= now:
                execute_job(job)
        await asyncio.sleep(1)  # 每秒检查一次
```
**问题**：
- CPU 空转：99% 的时间在无意义检查
- 延迟不可控：最多 1 秒延迟
- 精度与资源消耗矛盾：想要高精度就得频繁轮询

#### ✓ CronService 的事件驱动方式

```python
def _arm_timer(self) -> None:
    """精准定时器机制"""
    # 1. 取消旧定时器
    if self._timer_task:
        self._timer_task.cancel()

    # 2. 找到最早的下次运行时间
    next_wake = self._get_next_wake_ms()
    if not next_wake or not self._running:
        return

    # 3. 计算精确延迟
    delay_ms = max(0, next_wake - _now_ms())
    delay_s = delay_ms / 1000

    # 4. 创建定时器任务（关键：只等待到确切时间）
    async def tick():
        await asyncio.sleep(delay_s)  # 精准等待
        if self._running:
            await self._on_timer()

    self._timer_task = asyncio.create_task(tick())
```

**优势**：
- **零空转**：只在需要时唤醒
- **精确调度**：误差 ≈ asyncio 调度精度（通常 < 1ms）
- **自适应**：添加/删除任务后自动重新计算

### 定时器生命周期

```
[启动服务] start()
    ├─ _load_store()           # 从 JSON 加载任务
    ├─ _recompute_next_runs()  # 批量计算所有任务的下次运行
    ├─ _save_store()
    └─ _arm_timer()            # 启动第一个定时器
        ↓
[定时器等待] asyncio.sleep(delay_s)
        ↓
[时间到达] _on_timer()
    ├─ 扫描所有到期任务（now >= next_run_at_ms）
    ├─ 依次执行：_execute_job(job)
    │   ├─ 调用 on_job 回调
    │   ├─ 更新 state（last_run_at_ms, last_status）
    │   └─ 重新计算 next_run_at_ms
    ├─ _save_store()          # 批量保存所有变更
    └─ _arm_timer()           # 启动下一个定时器（递归循环）
```

### _get_next_wake_ms() - 查找最早任务

```python
def _get_next_wake_ms(self) -> int | None:
    if not self._store:
        return None

    # 收集所有启用任务的下次运行时间
    times = [
        j.state.next_run_at_ms
        for j in self._store.jobs
        if j.enabled and j.state.next_run_at_ms
    ]

    # 返回最小值（最早的时间）
    return min(times) if times else None
```

**算法复杂度**：O(n)，n = 任务数量
**优化空间**：可以用最小堆优化到 O(log n)，但 n 通常很小（< 100）

---

## 持久化设计

### JSON Schema 映射

**Python dataclass → JSON 的命名转换**：
```python
# Python 字段名（snake_case）
next_run_at_ms: int

# JSON 字段名（camelCase）
"nextRunAtMs": 1741946400000
```

**映射表**：

| Python 字段 | JSON 字段 | 类型 |
|------------|----------|------|
| `at_ms` | `atMs` | int |
| `every_ms` | `everyMs` | int |
| `next_run_at_ms` | `nextRunAtMs` | int |
| `last_run_at_ms` | `lastRunAtMs` | int |
| `created_at_ms` | `createdAtMs` | int |
| `updated_at_ms` | `updatedAtMs` | int |
| `delete_after_run` | `deleteAfterRun` | bool |

**为什么这样设计**？
- JSON 通常用 camelCase（JavaScript 传统）
- Python 用 snake_case（PEP 8 规范）
- 手动映射保证了跨语言兼容性

### 序列化/反序列化实现

#### 序列化（Python → JSON）

```python
def _save_store(self) -> None:
    data = {
        "version": self._store.version,
        "jobs": [
            {
                "id": j.id,
                "name": j.name,
                "schedule": {
                    "kind": j.schedule.kind,
                    "atMs": j.schedule.at_ms,      # 手动映射
                    "everyMs": j.schedule.every_ms,
                    "expr": j.schedule.expr,
                    "tz": j.schedule.tz,
                },
                # ... 其他字段
            }
            for j in self._store.jobs
        ]
    }

    # 关键参数
    self.store_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),  # 支持中文
        encoding="utf-8"
    )
```

**ensure_ascii=False 的作用**：
```python
# ensure_ascii=True（默认）
{"name": "\u4efb\u52a1"}  # 中文被转义

# ensure_ascii=False
{"name": "任务"}  # 中文原样保留
```

#### 反序列化（JSON → Python）

```python
def _load_store(self) -> CronStore:
    if self.store_path.exists():
        try:
            data = json.loads(self.store_path.read_text(encoding="utf-8"))
            jobs = []
            for j in data.get("jobs", []):
                jobs.append(CronJob(
                    id=j["id"],
                    schedule=CronSchedule(
                        kind=j["schedule"]["kind"],
                        at_ms=j["schedule"].get("atMs"),  # 手动映射回来
                        every_ms=j["schedule"].get("everyMs"),
                        # ...
                    ),
                    # ...
                ))
            return CronStore(jobs=jobs)
        except Exception as e:
            logger.warning("Failed to load cron store: {}", e)
            return CronStore()  # 容错：返回空存储
```

**容错设计**：
- 文件不存在 → 返回空 `CronStore()`
- JSON 解析失败 → 返回空 `CronStore()`
- 记录警告日志但不中断服务

### 存储时机分析

```python
# 读操作（不保存）
list_jobs()     # 只读

# 写操作（立即保存）
add_job()       # 添加后 → _save_store()
remove_job()    # 删除后 → _save_store()
enable_job()    # 修改后 → _save_store()

# 批量操作（延迟保存）
_on_timer()     # 执行所有到期任务后 → 一次 _save_store()
```

**优化点**：
- 批量执行避免频繁 I/O
- 每次操作都保存，保证数据不丢失（即使服务崩溃）

---

## 生命周期管理

### 启动流程详解

```python
async def start(self) -> None:
    # 1. 标记运行状态
    self._running = True

    # 2. 加载持久化数据
    self._load_store()
    # → 此时 self._store.jobs 已填充
    # → 但所有任务的 next_run_at_ms 可能是旧值（上次关闭时的值）

    # 3. 重新计算所有任务的下次运行时间
    self._recompute_next_runs()
    # → 关键！防止服务停止期间错过的任务立即执行

    # 举例：
    # - 任务配置：每天 9:00 AM
    # - 上次关闭时间：3月14日 20:00
    # - 存储的 next_run_at_ms：3月15日 09:00
    # - 当前时间：3月16日 08:00（服务停了1天多）
    # - 如果不重算：任务会在16日 09:00执行（正确）
    # - 但如果当前是16日 10:00（已过9点）
    #   → 重算后 next_run_at_ms = 3月17日 09:00（跳过过期的）

    # 4. 保存更新后的状态
    self._save_store()

    # 5. 启动定时器
    self._arm_timer()

    logger.info("Cron service started with {} jobs", len(self._store.jobs))
```

**_recompute_next_runs() 的重要性**：

```python
def _recompute_next_runs(self) -> None:
    now = _now_ms()
    for job in self._store.jobs:
        if job.enabled:
            # 从当前时间重新计算，不使用存储的旧值
            job.state.next_run_at_ms = _compute_next_run(job.schedule, now)
```

**场景分析**：

| 场景 | 不重算 | 重算后 |
|------|-------|--------|
| 服务停止1小时，任务每5分钟 | 启动后立即执行积压的12次 | 从当前时间起，5分钟后执行 |
| 服务停止1天，任务每天9点 | 启动时已过9点则立即执行 | 跳过今天，明天9点执行 |
| 服务停止期间，一次性任务到期 | 启动后执行过期任务 | 返回 None，任务不再执行 |

### 停止流程

```python
def stop(self) -> None:
    # 1. 标记停止状态
    self._running = False

    # 2. 取消定时器任务
    if self._timer_task:
        self._timer_task.cancel()  # asyncio.Task.cancel()
        self._timer_task = None

    # 注意：不保存状态！
    # - 已加载的数据仍在 self._store 中
    # - 如果有未保存的变更会丢失
    # - 下次 start() 会从磁盘重新加载
```

### 任务执行后的处理逻辑

```python
async def _execute_job(self, job: CronJob) -> None:
    start_ms = _now_ms()

    # 1. 执行回调
    try:
        if self.on_job:
            _response = await self.on_job(job)
        job.state.last_status = "ok"
        job.state.last_error = None
    except Exception as e:
        job.state.last_status = "error"
        job.state.last_error = str(e)

    # 2. 更新执行时间
    job.state.last_run_at_ms = start_ms
    job.updated_at_ms = _now_ms()

    # 3. 根据模式决定下一步
    if job.schedule.kind == "at":
        # 一次性任务
        if job.delete_after_run:
            # 从列表中删除
            self._store.jobs = [j for j in self._store.jobs if j.id != job.id]
        else:
            # 禁用但保留（用户可查看历史）
            job.enabled = False
            job.state.next_run_at_ms = None
    else:
        # 循环任务（every/cron）
        job.state.next_run_at_ms = _compute_next_run(job.schedule, _now_ms())

    # 注意：保存由 _on_timer() 负责（批量保存）
```

**delete_after_run 的设计意图**：

```python
# 场景1：临时提醒（用完即删）
job = service.add_job(
    name="meeting reminder",
    schedule=CronSchedule(kind="at", at_ms=...),
    message="Meeting in 5 minutes",
    delete_after_run=True,  # 执行后删除
)

# 场景2：归档历史（禁用但保留）
job = service.add_job(
    name="important reminder",
    schedule=CronSchedule(kind="at", at_ms=...),
    message="Critical deadline",
    delete_after_run=False,  # 执行后禁用，可查看历史
)
# 后续可通过 list_jobs(include_disabled=True) 查看
```

---

## 错误处理策略

### 1. 验证层（添加任务时）

```python
def _validate_schedule_for_add(schedule: CronSchedule) -> None:
    # 规则1：tz 只能用于 cron 模式
    if schedule.tz and schedule.kind != "cron":
        raise ValueError("tz can only be used with cron schedules")

    # 规则2：验证时区有效性
    if schedule.kind == "cron" and schedule.tz:
        try:
            from zoneinfo import ZoneInfo
            ZoneInfo(schedule.tz)  # 如果时区无效会抛出异常
        except Exception:
            raise ValueError(f"unknown timezone '{schedule.tz}'") from None
```

**为什么需要验证**？
- 提前发现配置错误，避免创建不可运行的任务
- 用户友好的错误消息，明确指出问题所在

### 2. 计算层（时间计算时）

```python
def _compute_next_run(schedule: CronSchedule, now_ms: int) -> int | None:
    if schedule.kind == "cron" and schedule.expr:
        try:
            from croniter import croniter
            from zoneinfo import ZoneInfo
            # ... 计算逻辑 ...
            return int(next_dt.timestamp() * 1000)
        except Exception:
            return None  # 静默失败，返回 None
    return None
```

**静默失败的设计**：
- 不抛出异常，返回 `None` 表示"无法调度"
- 任务保留在列表中但 `next_run_at_ms = None`
- 不影响其他任务的调度

**效果**：
```python
# 假设有10个任务，其中1个 cron 表达式错误
jobs = [
    job1,  # next_run_at_ms = 1000
    job2,  # next_run_at_ms = None  ← 计算失败
    job3,  # next_run_at_ms = 2000
    # ...
]

# _get_next_wake_ms() 会跳过 job2
times = [j.state.next_run_at_ms for j in jobs if j.state.next_run_at_ms]
# times = [1000, 2000, ...]  ← job2 被自动忽略

# 服务继续正常运行，只有 job2 不执行
```

### 3. 执行层（任务运行时）

```python
async def _execute_job(self, job: CronJob) -> None:
    try:
        if self.on_job:
            _response = await self.on_job(job)
        job.state.last_status = "ok"
        job.state.last_error = None
        logger.info("Cron: job '{}' completed", job.name)

    except Exception as e:
        # 捕获所有异常，记录但不中断
        job.state.last_status = "error"
        job.state.last_error = str(e)
        logger.error("Cron: job '{}' failed: {}", job.name, e)

    # 无论成功失败，都继续执行后续逻辑
    job.state.last_run_at_ms = start_ms
    # ...
```

**容错设计的价值**：
- 一个任务失败不影响其他任务
- 错误信息保存到 `last_error`，可事后查看
- 失败的任务仍会按计划重试（next_run_at_ms 已计算好）

### 4. 持久化层（存储失败时）

```python
def _load_store(self) -> CronStore:
    if self.store_path.exists():
        try:
            data = json.loads(self.store_path.read_text(encoding="utf-8"))
            # ... 解析逻辑 ...
            return CronStore(jobs=jobs)
        except Exception as e:
            logger.warning("Failed to load cron store: {}", e)
            return CronStore()  # 返回空存储，从头开始
    else:
        return CronStore()
```

**降级策略**：
- JSON 解析失败 → 返回空存储
- 权限错误无法读取 → 返回空存储
- 服务仍能启动，但所有任务丢失

**改进空间**：
- 可以添加备份文件机制（jobs.json.bak）
- 可以尝试修复损坏的 JSON（移除非法条目）

---

## 集成机制

### 1. 依赖注入模式

**CronService 不知道"如何执行任务"**：
```python
class CronService:
    def __init__(
        self,
        store_path: Path,
        on_job: Callable[[CronJob], Coroutine[Any, Any, str | None]] | None = None
    ):
        self.on_job = on_job  # 回调函数注入
```

**外部注入执行逻辑**（commands.py）：
```python
# 定义回调函数
async def on_cron_job(job: CronJob) -> str | None:
    # 这里可以做任何事：
    # - 调用 AgentLoop 处理消息
    # - 发送 HTTP 请求
    # - 写入数据库
    # - 发送通知
    response = await agent.process_direct(
        job.payload.message,
        session_key=f"cron:{job.id}",
        channel=job.payload.channel or "cli",
        chat_id=job.payload.to or "direct",
    )

    # 可选：投递到外部渠道
    if job.payload.deliver and job.payload.to:
        await bus.publish_outbound(OutboundMessage(
            channel=job.payload.channel or "cli",
            chat_id=job.payload.to,
            content=response or ""
        ))

    return response

# 注入回调
cron.on_job = on_cron_job
```

**依赖注入的好处**：
- CronService 是纯调度引擎，不依赖 AgentLoop
- 可以在不同环境中复用（CLI、Web、测试）
- 易于单元测试（注入 mock 函数）

### 2. CronTool - Agent 交互层

**CronTool 的职责**：
- 将 CronService 的功能暴露给 AI agent
- 自动管理会话上下文（channel, chat_id）
- 参数验证和错误提示

**关键设计**：
```python
class CronTool(Tool):
    def __init__(self, cron_service: CronService):
        self._cron = cron_service  # 持有 CronService 引用
        self._channel = ""         # 会话上下文
        self._chat_id = ""

    def set_context(self, channel: str, chat_id: str) -> None:
        """AgentLoop 在每次对话时调用"""
        self._channel = channel
        self._chat_id = chat_id

    async def execute(self, action: str, ...) -> str:
        if action == "add":
            return self._add_job(...)  # 转发到 CronService
        # ...
```

**会话上下文的传递**：
```
用户消息（Telegram chat_id=123456789）
    ↓
AgentLoop.process_direct(channel="telegram", chat_id="123456789")
    ↓
AgentLoop._set_tool_context()
    ↓
CronTool.set_context(channel="telegram", chat_id="123456789")
    ↓
Agent 决定使用 cron 工具
    ↓
CronTool.execute(action="add", message="每天9点提醒我")
    ↓
CronTool._add_job()
    ├─ 读取 self._channel = "telegram"
    ├─ 读取 self._chat_id = "123456789"
    └─ CronService.add_job(
        ...,
        channel="telegram",  # 自动填充
        to="123456789",      # 自动填充
        deliver=True
       )
    ↓
任务存储到 JSON，包含投递目标信息
```

**执行时的回溯**：
```
定时器触发
    ↓
_execute_job(job)
    ↓
on_job(job)
    ↓
agent.process_direct(
    message=job.payload.message,
    channel=job.payload.channel,  # "telegram"（从任务读取）
    chat_id=job.payload.to         # "123456789"
)
    ↓
生成响应
    ↓
如果 job.payload.deliver == True
    ↓
bus.publish_outbound(
    channel="telegram",
    chat_id="123456789",
    content=response
)
    ↓
消息发送到 Telegram 聊天 123456789
```

### 3. AgentLoop 注册流程

**注册时机**（loop.py）：
```python
class AgentLoop:
    def __init__(self, ..., cron_service: CronService | None = None):
        self.cron_service = cron_service
        self._register_default_tools()

    def _register_default_tools(self):
        # ... 注册其他工具 ...

        if self.cron_service:
            # 条件注册：只有提供了 CronService 才注册 CronTool
            self.tools.register(CronTool(self.cron_service))
```

**为什么是条件注册**？
- 不是所有场景都需要定时任务（如单次对话）
- 避免不必要的依赖（测试时可以不提供 CronService）

---

## 实战示例

### 示例1：创建简单的提醒系统

```python
import asyncio
from pathlib import Path
from nanobot.cron.service import CronService
from nanobot.cron.types import CronSchedule, CronJob

# 回调函数
async def on_reminder(job: CronJob) -> str | None:
    print(f"⏰ 提醒：{job.payload.message}")
    return "Reminder sent"

# 创建服务
service = CronService(
    store_path=Path("./reminders.json"),
    on_job=on_reminder
)

# 启动服务
await service.start()

# 添加任务
import time

# 1分钟后提醒
job1 = service.add_job(
    name="meeting",
    schedule=CronSchedule(
        kind="at",
        at_ms=int((time.time() + 60) * 1000)
    ),
    message="会议开始了！",
    delete_after_run=True
)

# 每30秒喝水提醒
job2 = service.add_job(
    name="drink_water",
    schedule=CronSchedule(
        kind="every",
        every_ms=30000
    ),
    message="该喝水了 💧"
)

# 每天早上9点
job3 = service.add_job(
    name="daily_standup",
    schedule=CronSchedule(
        kind="cron",
        expr="0 9 * * *",
        tz="Asia/Shanghai"
    ),
    message="准备站会"
)

# 保持运行
await asyncio.sleep(3600)  # 运行1小时

# 停止服务
service.stop()
```

### 示例2：集成到自定义 Agent

```python
from nanobot.cron.service import CronService
from nanobot.agent.loop import AgentLoop

class MyAgent:
    def __init__(self):
        # 创建 CronService
        self.cron = CronService(
            store_path=Path("~/.my_agent/cron/jobs.json")
        )

        # 创建 AgentLoop
        self.agent = AgentLoop(
            # ... 其他参数 ...
            cron_service=self.cron  # 传入 CronService
        )

        # 设置回调
        self.cron.on_job = self._handle_cron_job

    async def _handle_cron_job(self, job: CronJob) -> str | None:
        """处理定时任务"""
        print(f"执行定时任务: {job.name}")

        # 使用 agent 处理任务消息
        response = await self.agent.process_direct(
            message=job.payload.message,
            session_key=f"cron:{job.id}",
            channel=job.payload.channel or "cli",
            chat_id=job.payload.to or "system"
        )

        return response

    async def start(self):
        """启动 agent 和 cron 服务"""
        await self.cron.start()
        print("Agent started with cron support")

    def stop(self):
        """停止服务"""
        self.cron.stop()
        print("Agent stopped")

# 使用
agent = MyAgent()
await agent.start()

# 现在 AI agent 可以通过 cron 工具创建定时任务
# 用户：请每天早上9点提醒我查看邮件
# Agent 会调用：cron tool with action="add", cron_expr="0 9 * * *"
```

### 示例3：手动运行和测试

```python
# 测试定时任务而不等待
service = CronService(Path("./test_cron.json"))
await service.start()

# 添加一个本应在明天执行的任务
job = service.add_job(
    name="tomorrow_task",
    schedule=CronSchedule(
        kind="cron",
        expr="0 9 * * *",  # 明天9点
        tz="Asia/Shanghai"
    ),
    message="测试任务"
)

print(f"任务已创建，ID: {job.id}")
print(f"下次运行: {job.state.next_run_at_ms}")

# 不等待到明天，立即手动执行
success = await service.run_job(job.id)
print(f"手动执行: {'成功' if success else '失败'}")

# 查看执行结果
jobs = service.list_jobs(include_disabled=True)
for j in jobs:
    if j.id == job.id:
        print(f"最后状态: {j.state.last_status}")
        print(f"最后运行: {j.state.last_run_at_ms}")
        print(f"下次运行: {j.state.next_run_at_ms}")
```

---

## 总结

### CronService 的设计精髓

1. **分层架构**：
   - 数据层（types.py）- 纯数据结构
   - 业务层（service.py）- 调度逻辑
   - 接口层（cron.py）- Agent 交互

2. **设计模式**：
   - 依赖注入：`on_job` 回调
   - 策略模式：三种调度策略（at/every/cron）
   - 观察者模式：定时器触发执行
   - 仓储模式：CronStore 抽象存储

3. **核心技术**：
   - asyncio 事件循环
   - croniter 库解析 cron 表达式
   - zoneinfo 时区处理
   - JSON 持久化

4. **可靠性保障**：
   - 多层错误处理
   - 容错降级策略
   - 状态持久化
   - 重启自动恢复

### 学习路径建议

1. **基础阶段**：
   - 理解三种调度模式的差异
   - 掌握时间计算逻辑
   - 熟悉 JSON 序列化

2. **进阶阶段**：
   - 理解事件驱动机制
   - 掌握依赖注入模式
   - 学习时区处理

3. **高级阶段**：
   - 优化性能（最小堆）
   - 添加分布式支持
   - 实现任务优先级

### 扩展方向

1. **功能增强**：
   - 任务优先级
   - 任务依赖关系
   - 失败重试策略
   - 任务并发限制

2. **监控告警**：
   - Prometheus metrics
   - 任务执行统计
   - 失败率监控

3. **分布式支持**：
   - Redis 存储
   - 分布式锁
   - 多实例协调

4. **UI 管理界面**：
   - Web 控制台
   - 任务可视化
   - 实时日志

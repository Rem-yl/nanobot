"""Cron service for scheduling agent tasks."""

import asyncio
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Coroutine

from loguru import logger

from nanobot.cron.types import CronJob, CronJobState, CronPayload, CronSchedule, CronStore


def _now_ms() -> int:
    return int(time.time() * 1000)


def _compute_next_run(schedule: CronSchedule, now_ms: int) -> int | None:
    """Compute next run time in ms.

    Calculates the next execution timestamp based on schedule type:

    - "at" mode: Returns at_ms if it's in the future, else None (job expired).
    - "every" mode: Returns now_ms + every_ms (fixed interval from current time).
    - "cron" mode: Uses croniter to parse cron expression and compute next occurrence
      in the specified timezone (defaults to system timezone if tz not provided).

    Args:
        schedule: CronSchedule defining the timing rules.
        now_ms: Current reference time in milliseconds since epoch.

    Returns:
        Next execution timestamp in milliseconds, or None if schedule is invalid
        or job has expired (at mode only).
    """
    if schedule.kind == "at":
        return schedule.at_ms if schedule.at_ms and schedule.at_ms > now_ms else None

    if schedule.kind == "every":
        if not schedule.every_ms or schedule.every_ms <= 0:
            return None
        # Next interval from now
        return now_ms + schedule.every_ms

    if schedule.kind == "cron" and schedule.expr:
        try:
            from croniter import croniter
            from zoneinfo import ZoneInfo
            # Use caller-provided reference time for deterministic scheduling
            base_time = now_ms / 1000
            tz = ZoneInfo(schedule.tz) if schedule.tz else datetime.now().astimezone().tzinfo
            base_dt = datetime.fromtimestamp(base_time, tz=tz)
            cron = croniter(schedule.expr, base_dt)
            next_dt = cron.get_next(datetime)
            return int(next_dt.timestamp() * 1000)
        except Exception:
            return None

    return None


def _validate_schedule_for_add(schedule: CronSchedule) -> None:
    """Validate schedule fields that would otherwise create non-runnable jobs."""
    if schedule.tz and schedule.kind != "cron":
        raise ValueError("tz can only be used with cron schedules")

    if schedule.kind == "cron" and schedule.tz:
        try:
            from zoneinfo import ZoneInfo

            ZoneInfo(schedule.tz)
        except Exception:
            raise ValueError(f"unknown timezone '{schedule.tz}'") from None


class CronService:
    """Service for managing and executing scheduled jobs.

    CronService is a persistent, event-driven job scheduler that supports three scheduling modes:
    - One-time execution ("at" mode): Run at specific timestamp
    - Recurring intervals ("every" mode): Run every N milliseconds
    - Cron expressions ("cron" mode): Unix-style cron with timezone support

    Jobs are persisted to JSON storage and automatically executed via async timer mechanism.
    When jobs become due, the service invokes the on_job callback for execution.

    Attributes:
        store_path: Path to JSON file for persistent storage.
        on_job: Optional callback invoked when jobs execute. Receives CronJob,
            returns optional response text.

    Example:
        Basic usage with callback::

            async def handle_job(job: CronJob) -> str | None:
                print(f"Job '{job.name}' executed: {job.payload.message}")
                return "Job completed"

            service = CronService(Path("~/.nanobot/data/cron/jobs.json"), on_job=handle_job)
            await service.start()

            # Add a one-time job
            job = service.add_job(
                name="reminder",
                schedule=CronSchedule(kind="at", at_ms=int(time.time() * 1000) + 60000),
                message="This will execute in 60 seconds"
            )

    Integration:
        CronService integrates with nanobot through:

        - CLI: Instantiated in commands.py, on_job callback calls agent.process_direct()
        - AgentLoop: Registers CronTool when CronService is provided
        - CronTool: Provides agent actions (add/list/remove) with session context
    """
    
    def __init__(
        self,
        store_path: Path,
        on_job: Callable[[CronJob], Coroutine[Any, Any, str | None]] | None = None
    ):
        self.store_path = store_path
        self.on_job = on_job  # Callback to execute job, returns response text
        self._store: CronStore | None = None
        self._timer_task: asyncio.Task | None = None
        self._running = False
    
    def _load_store(self) -> CronStore:
        """Load jobs from disk."""
        if self._store:
            return self._store
        
        if self.store_path.exists():
            try:
                data = json.loads(self.store_path.read_text(encoding="utf-8"))
                jobs = []
                for j in data.get("jobs", []):
                    jobs.append(CronJob(
                        id=j["id"],
                        name=j["name"],
                        enabled=j.get("enabled", True),
                        schedule=CronSchedule(
                            kind=j["schedule"]["kind"],
                            at_ms=j["schedule"].get("atMs"),
                            every_ms=j["schedule"].get("everyMs"),
                            expr=j["schedule"].get("expr"),
                            tz=j["schedule"].get("tz"),
                        ),
                        payload=CronPayload(
                            kind=j["payload"].get("kind", "agent_turn"),
                            message=j["payload"].get("message", ""),
                            deliver=j["payload"].get("deliver", False),
                            channel=j["payload"].get("channel"),
                            to=j["payload"].get("to"),
                        ),
                        state=CronJobState(
                            next_run_at_ms=j.get("state", {}).get("nextRunAtMs"),
                            last_run_at_ms=j.get("state", {}).get("lastRunAtMs"),
                            last_status=j.get("state", {}).get("lastStatus"),
                            last_error=j.get("state", {}).get("lastError"),
                        ),
                        created_at_ms=j.get("createdAtMs", 0),
                        updated_at_ms=j.get("updatedAtMs", 0),
                        delete_after_run=j.get("deleteAfterRun", False),
                    ))
                self._store = CronStore(jobs=jobs)
            except Exception as e:
                logger.warning("Failed to load cron store: {}", e)
                self._store = CronStore()
        else:
            self._store = CronStore()
        
        return self._store
    
    def _save_store(self) -> None:
        """Save jobs to disk."""
        if not self._store:
            return
        
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "version": self._store.version,
            "jobs": [
                {
                    "id": j.id,
                    "name": j.name,
                    "enabled": j.enabled,
                    "schedule": {
                        "kind": j.schedule.kind,
                        "atMs": j.schedule.at_ms,
                        "everyMs": j.schedule.every_ms,
                        "expr": j.schedule.expr,
                        "tz": j.schedule.tz,
                    },
                    "payload": {
                        "kind": j.payload.kind,
                        "message": j.payload.message,
                        "deliver": j.payload.deliver,
                        "channel": j.payload.channel,
                        "to": j.payload.to,
                    },
                    "state": {
                        "nextRunAtMs": j.state.next_run_at_ms,
                        "lastRunAtMs": j.state.last_run_at_ms,
                        "lastStatus": j.state.last_status,
                        "lastError": j.state.last_error,
                    },
                    "createdAtMs": j.created_at_ms,
                    "updatedAtMs": j.updated_at_ms,
                    "deleteAfterRun": j.delete_after_run,
                }
                for j in self._store.jobs
            ]
        }
        
        self.store_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    
    async def start(self) -> None:
        """Start the cron service.

        Loads jobs from persistent storage, recomputes next run times for all enabled jobs,
        and starts the timer mechanism for automatic execution.

        Example::

            service = CronService(Path("~/.nanobot/data/cron/jobs.json"))
            await service.start()
            # Service is now running and will execute scheduled jobs
        """
        self._running = True
        self._load_store()
        self._recompute_next_runs()
        self._save_store()
        self._arm_timer()
        logger.info("Cron service started with {} jobs", len(self._store.jobs if self._store else []))
    
    def stop(self) -> None:
        """Stop the cron service.

        Cancels the timer task and prevents further job executions. Does not remove
        jobs from storage.

        Example::

            service.stop()
            # Service is stopped, no jobs will execute
        """
        self._running = False
        if self._timer_task:
            self._timer_task.cancel()
            self._timer_task = None
    
    def _recompute_next_runs(self) -> None:
        """Recompute next run times for all enabled jobs."""
        if not self._store:
            return
        now = _now_ms()
        for job in self._store.jobs:
            if job.enabled:
                job.state.next_run_at_ms = _compute_next_run(job.schedule, now)
    
    def _get_next_wake_ms(self) -> int | None:
        """Get the earliest next run time across all jobs."""
        if not self._store:
            return None
        times = [j.state.next_run_at_ms for j in self._store.jobs 
                 if j.enabled and j.state.next_run_at_ms]
        return min(times) if times else None
    
    def _arm_timer(self) -> None:
        """Schedule the next timer tick.

        Cancels any existing timer and creates a new async task to wake at the earliest
        next_run_at_ms across all enabled jobs. When the timer fires, executes all due
        jobs and reschedules itself for the next wake time.

        This mechanism ensures jobs execute at the correct time without polling, and
        automatically adapts when jobs are added/removed/modified.
        """
        if self._timer_task:
            self._timer_task.cancel()

        next_wake = self._get_next_wake_ms()
        if not next_wake or not self._running:
            return

        delay_ms = max(0, next_wake - _now_ms())
        delay_s = delay_ms / 1000

        async def tick():
            await asyncio.sleep(delay_s)
            if self._running:
                await self._on_timer()

        self._timer_task = asyncio.create_task(tick())
    
    async def _on_timer(self) -> None:
        """Handle timer tick - run due jobs."""
        if not self._store:
            return
        
        now = _now_ms()
        due_jobs = [
            j for j in self._store.jobs
            if j.enabled and j.state.next_run_at_ms and now >= j.state.next_run_at_ms
        ]
        
        for job in due_jobs:
            await self._execute_job(job)
        
        self._save_store()
        self._arm_timer()
    
    async def _execute_job(self, job: CronJob) -> None:
        """Execute a single job.

        Invokes the on_job callback and updates job state based on execution result.
        Handles different post-execution behaviors:

        - "at" mode with delete_after_run=True: Removes job from storage
        - "at" mode with delete_after_run=False: Disables job and clears next_run_at_ms
        - "every"/"cron" mode: Computes next run time and updates next_run_at_ms

        Updates last_run_at_ms, last_status, and last_error regardless of success/failure.
        """
        start_ms = _now_ms()
        logger.info("Cron: executing job '{}' ({})", job.name, job.id)

        try:
            if self.on_job:
                _response = await self.on_job(job)

            job.state.last_status = "ok"
            job.state.last_error = None
            logger.info("Cron: job '{}' completed", job.name)

        except Exception as e:
            job.state.last_status = "error"
            job.state.last_error = str(e)
            logger.error("Cron: job '{}' failed: {}", job.name, e)

        job.state.last_run_at_ms = start_ms
        job.updated_at_ms = _now_ms()

        # Handle one-shot jobs
        if job.schedule.kind == "at":
            if job.delete_after_run:
                self._store.jobs = [j for j in self._store.jobs if j.id != job.id]
            else:
                job.enabled = False
                job.state.next_run_at_ms = None
        else:
            # Compute next run
            job.state.next_run_at_ms = _compute_next_run(job.schedule, _now_ms())
    
    # ========== Public API ==========
    
    def list_jobs(self, include_disabled: bool = False) -> list[CronJob]:
        """List all jobs.

        Args:
            include_disabled: If True, include disabled jobs in results. Defaults to False.

        Returns:
            List of jobs sorted by next_run_at_ms (earliest first). Jobs with no
            next_run_at_ms appear last.

        Example::

            # List only enabled jobs
            jobs = service.list_jobs()
            for job in jobs:
                print(f"{job.name}: next run at {job.state.next_run_at_ms}")

            # List all jobs including disabled
            all_jobs = service.list_jobs(include_disabled=True)
        """
        store = self._load_store()
        jobs = store.jobs if include_disabled else [j for j in store.jobs if j.enabled]
        return sorted(jobs, key=lambda j: j.state.next_run_at_ms or float('inf'))
    
    def add_job(
        self,
        name: str,
        schedule: CronSchedule,
        message: str,
        deliver: bool = False,
        channel: str | None = None,
        to: str | None = None,
        delete_after_run: bool = False,
    ) -> CronJob:
        """Add a new job.

        Creates a new scheduled job and persists it to storage. The job will be
        automatically executed at the scheduled time(s) via the on_job callback.

        Args:
            name: Human-readable job name for identification.
            schedule: CronSchedule defining when the job runs (at/every/cron mode).
            message: Message text to include in job payload (passed to on_job callback).
            deliver: If True, send response to specified channel. Defaults to False.
            channel: Target channel for delivery (e.g., "telegram", "whatsapp").
            to: Recipient identifier for delivery (e.g., chat_id, phone number).
            delete_after_run: If True, delete job after first execution. Only applies
                to "at" mode jobs. Defaults to False.

        Returns:
            The created CronJob with generated ID and computed next_run_at_ms.

        Raises:
            ValueError: If schedule validation fails (e.g., invalid timezone for cron mode).

        Example::

            # One-time job (at mode)
            job = service.add_job(
                name="reminder",
                schedule=CronSchedule(kind="at", at_ms=int(time.time() * 1000) + 60000),
                message="Meeting in 1 minute!",
                delete_after_run=True
            )

            # Recurring job (every mode) - every 5 seconds
            job = service.add_job(
                name="heartbeat",
                schedule=CronSchedule(kind="every", every_ms=5000),
                message="System check"
            )

            # Cron expression (cron mode) - daily at 9 AM Vancouver time
            job = service.add_job(
                name="daily_report",
                schedule=CronSchedule(kind="cron", expr="0 9 * * *", tz="America/Vancouver"),
                message="Generate daily report",
                deliver=True,
                channel="telegram",
                to="123456789"
            )
        """
        store = self._load_store()
        _validate_schedule_for_add(schedule)
        now = _now_ms()
        
        job = CronJob(
            id=str(uuid.uuid4())[:8],
            name=name,
            enabled=True,
            schedule=schedule,
            payload=CronPayload(
                kind="agent_turn",
                message=message,
                deliver=deliver,
                channel=channel,
                to=to,
            ),
            state=CronJobState(next_run_at_ms=_compute_next_run(schedule, now)),
            created_at_ms=now,
            updated_at_ms=now,
            delete_after_run=delete_after_run,
        )
        
        store.jobs.append(job)
        self._save_store()
        self._arm_timer()
        
        logger.info("Cron: added job '{}' ({})", name, job.id)
        return job
    
    def remove_job(self, job_id: str) -> bool:
        """Remove a job by ID.

        Permanently deletes the job from storage and reschedules the timer.

        Args:
            job_id: The ID of the job to remove.

        Returns:
            True if the job was found and removed, False if job_id not found.

        Example::

            # Remove a job
            success = service.remove_job("abc12345")
            if success:
                print("Job removed successfully")
        """
        store = self._load_store()
        before = len(store.jobs)
        store.jobs = [j for j in store.jobs if j.id != job_id]
        removed = len(store.jobs) < before
        
        if removed:
            self._save_store()
            self._arm_timer()
            logger.info("Cron: removed job {}", job_id)
        
        return removed
    
    def enable_job(self, job_id: str, enabled: bool = True) -> CronJob | None:
        """Enable or disable a job.

        When enabling a job, recomputes next_run_at_ms based on current time. When
        disabling, clears next_run_at_ms to prevent execution.

        Args:
            job_id: The ID of the job to modify.
            enabled: If True, enable the job; if False, disable it. Defaults to True.

        Returns:
            The modified CronJob if found, None if job_id not found.

        Example::

            # Disable a job temporarily
            job = service.enable_job("abc12345", enabled=False)

            # Re-enable the job (recalculates next run time)
            job = service.enable_job("abc12345", enabled=True)
        """
        store = self._load_store()
        for job in store.jobs:
            if job.id == job_id:
                job.enabled = enabled
                job.updated_at_ms = _now_ms()
                if enabled:
                    job.state.next_run_at_ms = _compute_next_run(job.schedule, _now_ms())
                else:
                    job.state.next_run_at_ms = None
                self._save_store()
                self._arm_timer()
                return job
        return None
    
    async def run_job(self, job_id: str, force: bool = False) -> bool:
        """Manually run a job.

        Executes the job immediately, bypassing the schedule. Updates job state
        (last_run_at_ms, next_run_at_ms) as if it executed normally.

        Args:
            job_id: The ID of the job to run.
            force: If True, run even if job is disabled. If False, only run enabled
                jobs. Defaults to False.

        Returns:
            True if the job was found and executed, False if job_id not found or
            job is disabled (when force=False).

        Example::

            # Run an enabled job immediately
            success = await service.run_job("abc12345")

            # Force run a disabled job
            success = await service.run_job("abc12345", force=True)
        """
        store = self._load_store()
        for job in store.jobs:
            if job.id == job_id:
                if not force and not job.enabled:
                    return False
                await self._execute_job(job)
                self._save_store()
                self._arm_timer()
                return True
        return False
    
    def status(self) -> dict:
        """Get service status.

        Returns:
            Dictionary containing:
                - enabled (bool): Whether the service is running.
                - jobs (int): Total number of jobs (including disabled).
                - next_wake_at_ms (int | None): Timestamp in milliseconds when the
                  next job will execute, or None if no jobs are scheduled.

        Example::

            status = service.status()
            print(f"Running: {status['enabled']}")
            print(f"Total jobs: {status['jobs']}")
            if status['next_wake_at_ms']:
                next_run = datetime.fromtimestamp(status['next_wake_at_ms'] / 1000)
                print(f"Next execution: {next_run}")
        """
        store = self._load_store()
        return {
            "enabled": self._running,
            "jobs": len(store.jobs),
            "next_wake_at_ms": self._get_next_wake_ms(),
        }

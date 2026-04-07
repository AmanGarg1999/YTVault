"""
LLM priority coordination for knowledgeVault-YT.

Refactored to use a global PriorityQueue, ensuring that UI-driven research 
queries (HIGH) take precedence over background ingestion tasks (LOW).
"""

import logging
import threading
import uuid
import queue
from concurrent.futures import Future
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Callable, Optional, Any

from src.config import get_settings

logger = logging.getLogger(__name__)


class LLMPriority(IntEnum):
    """Priority levels for LLM tasks. Lower value = higher priority."""
    HIGH = 0      # UI interactions, RAG queries
    MEDIUM = 1    # Epiphany Engine synthesis
    LOW = 2       # Background ingestion (Summarization, Analysis)


@dataclass(order=True)
class PrioritizedTask:
    """Internal wrapper for tasks in the priority queue."""
    priority: int
    timestamp: float  # For FIFO within same priority
    task_id: str = field(compare=False)
    fn: Callable = field(compare=False)
    args: tuple = field(compare=False, default_factory=tuple)
    kwargs: dict = field(compare=False, default_factory=dict)
    future: Future = field(compare=False, default_factory=Future)


# Global Coordinator State
_QUEUE = queue.PriorityQueue()
_MAX_CONCURRENCY = 8
_INITIALIZED = False
_INIT_LOCK = threading.Lock()


def _worker():
    """Background worker that pulls and executes tasks from the priority queue."""
    while True:
        prioritized_item = _QUEUE.get()
        if prioritized_item is None:
            break
            
        task = prioritized_item
        try:
            if not task.future.set_running_or_notify_cancel():
                continue
                
            result = task.fn(*task.args, **task.kwargs)
            task.future.set_result(result)
        except Exception as e:
            logger.error(f"Priority Task {task.task_id} failed: {e}")
            task.future.set_exception(e)
        finally:
            _QUEUE.task_done()


def ensure_initialized():
    """Start the coordinator workers if not already running."""
    global _INITIALIZED, _MAX_CONCURRENCY
    with _INIT_LOCK:
        if _INITIALIZED:
            return
            
        settings = get_settings()
        _MAX_CONCURRENCY = settings.get("pipeline", {}).get("llm_max_workers", 8)
        
        for i in range(_MAX_CONCURRENCY):
            t = threading.Thread(target=_worker, daemon=True, name=f"LLM-Worker-{i}")
            t.start()
            
        _INITIALIZED = True
        logger.info(f"LLM Priority Coordinator initialized with {_MAX_CONCURRENCY} workers")


@dataclass
class LLMTask:
    """A single LLM inference task."""
    task_id: str
    fn: Callable
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    priority: LLMPriority = LLMPriority.LOW


@dataclass
class LLMResult:
    """Result of an LLM inference task."""
    task_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None


class LLMPool:
    """Interface for submitting LLM tasks with priority."""

    def __init__(self, priority: LLMPriority = LLMPriority.LOW):
        self.default_priority = priority
        ensure_initialized()

    def submit(self, task: LLMTask) -> Future:
        """Submit a single task and return a Future."""
        import time
        
        future = Future()
        p_task = PrioritizedTask(
            priority=int(task.priority),
            timestamp=time.time(),
            task_id=task.task_id,
            fn=task.fn,
            args=task.args,
            kwargs=task.kwargs,
            future=future
        )
        _QUEUE.put(p_task)
        return future

    def submit_batch(
        self,
        tasks: list[LLMTask],
        on_complete: Optional[Callable[[LLMResult], None]] = None,
    ) -> list[LLMResult]:
        """Execute a batch of tasks and Wait for all to complete."""
        futures = {self.submit(t): t for t in tasks}
        results = []
        
        from concurrent.futures import as_completed
        for future in as_completed(futures):
            task = futures[future]
            try:
                res = future.result()
                results.append(LLMResult(task_id=task.task_id, success=True, result=res))
            except Exception as e:
                results.append(LLMResult(task_id=task.task_id, success=False, error=str(e)))
                
            if on_complete:
                on_complete(results[-1])
                
        return results

    def submit_map(
        self,
        fn: Callable,
        items: list,
        id_fn: Callable = None,
        priority: Optional[LLMPriority] = None
    ) -> list[LLMResult]:
        """Map a function over items with a specific priority."""
        p = priority if priority is not None else self.default_priority
        tasks = [
            LLMTask(
                task_id=id_fn(item) if id_fn else f"task_{uuid.uuid4().hex[:8]}",
                fn=fn,
                args=(item,),
                priority=p
            )
            for item in items
        ]
        return self.submit_batch(tasks)


def get_llm_semaphore():
    """Legacy helper for backward compatibility. Now returns a dummy context manager."""
    class DummyContext:
        def __enter__(self): pass
        def __exit__(self, *args): pass
    return DummyContext()

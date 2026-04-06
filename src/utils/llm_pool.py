"""
LLM batch execution pool for knowledgeVault-YT.

Provides a ThreadPoolExecutor-based pool for running multiple
Ollama inference calls concurrently, with configurable parallelism.
"""

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Optional

from src.config import get_settings

logger = logging.getLogger(__name__)

# Global semaphore to enforce strict concurrency across all LLMPool instances
_LLM_SEMAPHORE = None
_SEMAPHORE_LOCK = threading.Lock()

def get_llm_semaphore():
    """Get or initialize the global LLM concurrency semaphore."""
    global _LLM_SEMAPHORE
    with _SEMAPHORE_LOCK:
        if _LLM_SEMAPHORE is None:
            settings = get_settings()
            max_workers = settings.get("pipeline", {}).get("llm_max_workers", 8)
            _LLM_SEMAPHORE = threading.BoundedSemaphore(max_workers)
            logger.info(f"Global LLM Semaphore initialized with {max_workers} slots")
    return _LLM_SEMAPHORE


@dataclass
class LLMTask:
    """A single LLM inference task."""
    task_id: str
    fn: Callable
    args: tuple = ()
    kwargs: dict = None

    def __post_init__(self):
        if self.kwargs is None:
            self.kwargs = {}


@dataclass
class LLMResult:
    """Result of an LLM inference task."""
    task_id: str
    success: bool
    result: object = None
    error: Optional[str] = None


class LLMPool:
    """Thread pool for batching LLM inference calls.

    Now uses a global semaphore to ensure that total concurrent LLM calls
    across the entire application do not exceed pipeline.llm_max_workers.
    """

    def __init__(self, max_workers: Optional[int] = None):
        settings = get_settings()
        # Pool-specific limit (must be <= global limit to be meaningful)
        self.max_workers = max_workers or settings.get("pipeline", {}).get(
            "llm_max_workers", 8
        )
        self.semaphore = get_llm_semaphore()
        logger.debug(f"LLMPool instance created (pool limit: {self.max_workers})")

    def _execute_with_semaphore(self, task: LLMTask) -> object:
        """Worker wrapper that respects the global LLM concurrency limit."""
        with self.semaphore:
            return task.fn(*task.args, **task.kwargs)

    def submit_batch(
        self,
        tasks: list[LLMTask],
        on_complete: Optional[Callable[[LLMResult], None]] = None,
    ) -> list[LLMResult]:
        """Execute a batch of LLM tasks concurrently, respecting global limits.

        Args:
            tasks: List of LLMTask objects to execute.
            on_complete: Optional callback invoked after each task completes.

        Returns:
            List of LLMResult objects (in completion order, not submission order).
        """
        if not tasks:
            return []

        results = []

        # We still use a local ThreadPoolExecutor for this batch, 
        # but the actual execution is gated by the global semaphore.
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {
                executor.submit(self._execute_with_semaphore, task): task
                for task in tasks
            }

            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    llm_result = LLMResult(
                        task_id=task.task_id, success=True, result=result,
                    )
                except Exception as e:
                    logger.warning(
                        f"LLM task {task.task_id} failed: {e}"
                    )
                    llm_result = LLMResult(
                        task_id=task.task_id, success=False, error=str(e),
                    )

                results.append(llm_result)
                if on_complete:
                    on_complete(llm_result)

        logger.info(
            f"LLM batch complete: {sum(1 for r in results if r.success)}/"
            f"{len(results)} succeeded"
        )
        return results

    def submit_map(
        self,
        fn: Callable,
        items: list,
        id_fn: Callable = None,
    ) -> list[LLMResult]:
        """Convenience method: map a single function over a list of items.

        Args:
            fn: Function to call for each item. Signature: fn(item) -> result.
            items: List of items to process.
            id_fn: Optional function to extract a task ID from each item.
                   Defaults to using the item's index.

        Returns:
            List of LLMResult objects.
        """
        tasks = [
            LLMTask(
                task_id=id_fn(item) if id_fn else str(i),
                fn=fn,
                args=(item,),
            )
            for i, item in enumerate(items)
        ]
        return self.submit_batch(tasks)

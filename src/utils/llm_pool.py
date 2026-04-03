"""
LLM batch execution pool for knowledgeVault-YT.

Provides a ThreadPoolExecutor-based pool for running multiple
Ollama inference calls concurrently, with configurable parallelism.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Optional

from src.config import get_settings

logger = logging.getLogger(__name__)


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

    Usage:
        pool = LLMPool(max_workers=3)
        tasks = [
            LLMTask("video_1", triage_fn, args=(video_1,)),
            LLMTask("video_2", triage_fn, args=(video_2,)),
        ]
        results = pool.submit_batch(tasks)
    """

    def __init__(self, max_workers: Optional[int] = None):
        settings = get_settings()
        self.max_workers = max_workers or settings.get("pipeline", {}).get(
            "llm_max_workers", 2
        )
        logger.info(f"LLMPool initialized with {self.max_workers} workers")

    def submit_batch(
        self,
        tasks: list[LLMTask],
        on_complete: Optional[Callable[[LLMResult], None]] = None,
    ) -> list[LLMResult]:
        """Execute a batch of LLM tasks concurrently.

        Args:
            tasks: List of LLMTask objects to execute.
            on_complete: Optional callback invoked after each task completes.

        Returns:
            List of LLMResult objects (in completion order, not submission order).
        """
        if not tasks:
            return []

        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {
                executor.submit(task.fn, *task.args, **task.kwargs): task
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

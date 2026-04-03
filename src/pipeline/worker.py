"""
Process-based pipeline worker for knowledgeVault-YT.

Replaces fragile daemon threads with a proper multiprocessing.Process
worker that communicates status via a shared Queue.
"""

import logging
import multiprocessing
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class WorkerStatus(str, Enum):
    """Pipeline worker lifecycle states."""
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class WorkerMessage:
    """Status message sent from worker process to UI."""
    scan_id: str
    status: WorkerStatus
    detail: str = ""
    progress_current: int = 0
    progress_total: int = 0
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


def _run_pipeline_process(
    url: str,
    scan_id: Optional[str],
    status_queue: multiprocessing.Queue,
):
    """Entry point for the worker process.

    Runs the full pipeline and sends WorkerMessage updates via the queue.
    This function runs in a separate process — it must not reference
    any Streamlit state or module-level singletons.
    """
    from src.pipeline.orchestrator import PipelineOrchestrator

    current_scan_id = scan_id or "pending"

    def send_status(msg: str):
        """Send a status update to the UI via the queue."""
        try:
            status_queue.put_nowait(WorkerMessage(
                scan_id=current_scan_id,
                status=WorkerStatus.RUNNING,
                detail=msg,
            ))
        except Exception:
            pass  # Queue full or closed — don't block the pipeline

    try:
        status_queue.put_nowait(WorkerMessage(
            scan_id=current_scan_id,
            status=WorkerStatus.STARTING,
            detail=f"Initializing pipeline for {url}",
        ))

        pipeline = PipelineOrchestrator()
        pipeline.set_callbacks(on_status=send_status)

        if scan_id:
            pipeline.resume(scan_id)
        else:
            current_scan_id = pipeline.run(url)

        status_queue.put_nowait(WorkerMessage(
            scan_id=current_scan_id,
            status=WorkerStatus.COMPLETED,
            detail="Pipeline finished successfully",
        ))

    except Exception as e:
        logger.error(f"Pipeline worker failed: {e}", exc_info=True)
        status_queue.put_nowait(WorkerMessage(
            scan_id=current_scan_id,
            status=WorkerStatus.FAILED,
            detail=str(e)[:200],
        ))


class PipelineWorkerManager:
    """Manages pipeline worker processes and their status queues.

    Designed to be used from Streamlit — tracks active workers and
    provides methods to start, monitor, and drain status updates.

    Usage:
        manager = PipelineWorkerManager()
        worker_id = manager.start("https://youtube.com/@channel")

        # On each Streamlit rerun:
        messages = manager.drain_messages()
        for msg in messages:
            st.write(f"[{msg.scan_id}] {msg.status}: {msg.detail}")
    """

    def __init__(self):
        self._workers: dict[str, dict] = {}
        self._status_queue = multiprocessing.Queue(maxsize=1000)

    def start(self, url: str, scan_id: Optional[str] = None) -> str:
        """Start a new pipeline worker process.

        Args:
            url: YouTube URL to process.
            scan_id: Optional scan ID for resuming.

        Returns:
            Worker ID (scan_id or url).
        """
        worker_id = scan_id or url

        process = multiprocessing.Process(
            target=_run_pipeline_process,
            args=(url, scan_id, self._status_queue),
            daemon=True,
            name=f"pipeline-worker-{worker_id[:20]}",
        )

        self._workers[worker_id] = {
            "process": process,
            "url": url,
            "scan_id": scan_id,
            "start_time": time.time(),
        }

        process.start()
        logger.info(f"Started pipeline worker {worker_id} (PID: {process.pid})")
        return worker_id

    def is_running(self, worker_id: str) -> bool:
        """Check if a worker is still running."""
        worker = self._workers.get(worker_id)
        if worker and worker["process"].is_alive():
            return True
        return False

    def get_active_workers(self) -> list[str]:
        """Get IDs of all active workers."""
        active = []
        for wid, worker in list(self._workers.items()):
            if worker["process"].is_alive():
                active.append(wid)
            else:
                # Clean up finished workers
                worker["process"].join(timeout=0)
        return active

    def drain_messages(self) -> list[WorkerMessage]:
        """Non-blocking drain of all pending status messages.

        Call this on each Streamlit rerun to get updates.
        """
        messages = []
        while not self._status_queue.empty():
            try:
                msg = self._status_queue.get_nowait()
                messages.append(msg)
            except Exception:
                break
        return messages

    def stop(self, worker_id: str) -> None:
        """Forcefully terminate a worker process."""
        worker = self._workers.get(worker_id)
        if worker and worker["process"].is_alive():
            worker["process"].terminate()
            worker["process"].join(timeout=5)
            logger.warning(f"Terminated pipeline worker {worker_id}")

    def stop_all(self) -> None:
        """Terminate all active workers."""
        for wid in list(self._workers.keys()):
            self.stop(wid)
        self._workers.clear()

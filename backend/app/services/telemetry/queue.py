import asyncio
import logging
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional
from ...core.config import settings

logger = logging.getLogger("toursafe.telemetry.queue")


class TelemetryIngestionQueue:
    """
    Bounded asynchronous queue for non-blocking telemetry ingestion and persistence worker.
    Protects the realtime connection from backend backpressure and spikes.
    """

    def __init__(self, max_capacity: Optional[int] = None):
        self.capacity = max_capacity or settings.telemetry_max_queue_depth
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=self.capacity)
        self.enqueue_failures: int = 0
        self.processed_count: int = 0
        self.processing_latency_ms: float = 0.0
        self._worker_task: Optional[asyncio.Task] = None
        self._processor: Optional[Callable[[Any], Coroutine[Any, Any, None]]] = None

    def set_processor(self, processor: Callable[[Any], Coroutine[Any, Any, None]]):
        self._processor = processor

    def _ensure_worker(self):
        try:
            loop = asyncio.get_running_loop()
            if (
                self._worker_task is None
                or self._worker_task.done()
                or self._worker_task.get_loop() is not loop
                or self._worker_task.get_loop().is_closed()
            ):
                self._worker_task = loop.create_task(self._worker_loop())
        except RuntimeError:
            pass

    def start_worker(self):
        self._ensure_worker()

    async def _worker_loop(self):
        try:
            while not self._queue.empty():
                try:
                    item = self._queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                start = time.perf_counter()
                if self._processor:
                    try:
                        await self._processor(item)
                    except Exception as pe:
                        logger.error("Error processing telemetry queue item: %s", pe)
                self.processing_latency_ms = round((time.perf_counter() - start) * 1000.0, 2)
                self.processed_count += 1
                self._queue.task_done()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Unexpected error in telemetry queue worker: %s", e)
        finally:
            self._worker_task = None

    def enqueue(self, item: Any) -> bool:
        """
        Enqueues an item non-blockingly. If capacity is reached, applies bounded drop policy.
        """
        self._ensure_worker()
        try:
            self._queue.put_nowait(item)
            return True
        except asyncio.QueueFull:
            self.enqueue_failures += 1
            logger.warning(
                "Telemetry queue is FULL (depth=%d, capacity=%d). Enqueue rejected.",
                self._queue.qsize(),
                self.capacity,
            )
            return False

    @property
    def depth(self) -> int:
        return self._queue.qsize()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "queue_depth": self._queue.qsize(),
            "queue_capacity": self.capacity,
            "enqueue_failures": self.enqueue_failures,
            "processed_count": self.processed_count,
            "processing_latency_ms": self.processing_latency_ms,
        }

    def shutdown_sync(self):
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
        self._worker_task = None

    async def shutdown(self):
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        self._worker_task = None


telemetry_queue = TelemetryIngestionQueue()

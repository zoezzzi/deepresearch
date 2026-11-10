"""SSE event fan-out: keep subscriber queues per workflow_id and broadcast to them."""

import json
from asyncio import Queue, QueueFull
from datetime import datetime
from typing import Any

from harness.logger import logger


class DateTimeEncoder(json.JSONEncoder):
    """JSON encoder that renders ``datetime`` as ISO text so events never fail to serialize."""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class SSEEvent:
    """A pending SSE event; serializes itself to the text/event-stream wire format."""

    def __init__(self, event_type: str, data: Any, workflow_id: str):
        self.event_type = event_type
        self.data = data
        self.workflow_id = workflow_id

    def to_sse_format(self) -> str:
        """Render the event using the ``event:`` + ``data:`` wire format.

        If serialization fails, degrade to an error event: one unserializable
        field must not hand the client truncated data or crash the push coroutine.
        """
        try:
            payload = json.dumps(self.data, cls=DateTimeEncoder, ensure_ascii=False)
            event_type = self.event_type
        except (TypeError, ValueError) as e:
            logger.error(
                f"[SSE] 事件序列化失败，降级为 error 事件: "
                f"workflow={self.workflow_id}, event={self.event_type}, error={e}"
            )
            event_type = "error"
            payload = json.dumps(
                {
                    "workflow_id": self.workflow_id,
                    "message": "事件数据序列化失败",
                    "event_type": self.event_type,
                },
                ensure_ascii=False,
            )
        return f"event: {event_type}\ndata: {payload}\n\n"


class SSEConnectionManager:
    """In-process SSE subscription manager (singleton).

    Each SSE connection owns a dedicated queue; the manager only delivers to
    queues and never consumes them. ``__new__`` keeps a single connection table
    even if callers instantiate the class repeatedly.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._connections: dict[str, set[Queue]] = {}
        self._initialized = True
        logger.info("SSE Connection Manager initialized")

    async def connect(self, workflow_id: str, queue: Queue) -> None:
        """Register a subscriber queue for the workflow."""
        if workflow_id not in self._connections:
            self._connections[workflow_id] = set()
        self._connections[workflow_id].add(queue)
        logger.info(
            f"New connection for workflow {workflow_id}, total: {len(self._connections[workflow_id])}"
        )

    async def disconnect(self, workflow_id: str, queue: Queue) -> None:
        """Remove a subscriber queue; drop the workflow entry once empty."""
        if workflow_id in self._connections:
            self._connections[workflow_id].discard(queue)
            if not self._connections[workflow_id]:
                del self._connections[workflow_id]
            logger.info(f"Disconnected from workflow {workflow_id}")

    async def broadcast(self, event: SSEEvent) -> None:
        """Deliver the event to every subscriber of the workflow.

        Delivery is non-blocking: when a queue is full the oldest event is
        dropped to make room, so a slow client cannot back-pressure the workflow.
        Failed queues are collected first and removed afterwards, avoiding
        mutation while iterating the connection set.
        """
        workflow_id = event.workflow_id
        if workflow_id not in self._connections:
            logger.warning(
                f"[SSEManager] No connections for workflow {workflow_id}, event {event.event_type} will be lost"
            )
            return

        disconnected_queues = []
        success_count = 0
        for queue in self._connections[workflow_id]:
            try:
                try:
                    queue.put_nowait(event)
                except QueueFull:
                    # 丢弃最旧的一条，保证客户端仍能收到最新状态
                    try:
                        queue.get_nowait()
                    except Exception:
                        pass
                    queue.put_nowait(event)
                    logger.warning(
                        f"[SSEManager] 订阅队列已满，丢弃最旧事件: workflow={workflow_id}"
                    )
                success_count += 1
            except Exception as e:
                logger.error(f"[SSEManager] Error broadcasting to queue: {e}")
                disconnected_queues.append(queue)

        logger.info(
            f"[SSEManager] Broadcast {event.event_type} to {success_count} connections for workflow {workflow_id}"
        )

        for queue in disconnected_queues:
            await self.disconnect(workflow_id, queue)

    async def send_event(self, workflow_id: str, event_type: str, data: Any) -> None:
        """Convenience wrapper that builds an SSEEvent and broadcasts it."""
        logger.info(f"[SSEManager] Sending {event_type} event to workflow {workflow_id}")
        event = SSEEvent(event_type=event_type, data=data, workflow_id=workflow_id)
        await self.broadcast(event)

    def get_connection_count(self, workflow_id: str) -> int:
        """Number of active subscribers for a workflow (0 if none)."""
        return len(self._connections.get(workflow_id, set()))


def get_sse_manager() -> SSEConnectionManager:
    return SSEConnectionManager()

from typing import Dict, Set, Any
from asyncio import Queue
import json
from datetime import datetime
from harness.logger import logger


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class SSEEvent:
    def __init__(self, event_type: str, data: Any, workflow_id: str):
        self.event_type = event_type
        self.data = data
        self.workflow_id = workflow_id

    def to_sse_format(self) -> str:
        lines = []
        lines.append(f"event: {self.event_type}")
        lines.append(f"data: {json.dumps(self.data, cls=DateTimeEncoder)}")
        return "\n".join(lines) + "\n\n"


class SSEConnectionManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._connections: Dict[str, Set[Queue]] = {}
        self._initialized = True
        logger.info("SSE Connection Manager initialized")

    async def connect(self, workflow_id: str, queue: Queue) -> None:
        if workflow_id not in self._connections:
            self._connections[workflow_id] = set()
        self._connections[workflow_id].add(queue)
        logger.info(f"New connection for workflow {workflow_id}, total: {len(self._connections[workflow_id])}")

    async def disconnect(self, workflow_id: str, queue: Queue) -> None:
        if workflow_id in self._connections:
            self._connections[workflow_id].discard(queue)
            if not self._connections[workflow_id]:
                del self._connections[workflow_id]
            logger.info(f"Disconnected from workflow {workflow_id}")

    async def broadcast(self, event: SSEEvent) -> None:
        workflow_id = event.workflow_id
        if workflow_id not in self._connections:
            logger.warning(f"[SSEManager] No connections for workflow {workflow_id}, event {event.event_type} will be lost")
            return

        disconnected_queues = []
        success_count = 0
        for queue in self._connections[workflow_id]:
            try:
                await queue.put(event)
                success_count += 1
            except Exception as e:
                logger.error(f"[SSEManager] Error broadcasting to queue: {e}")
                disconnected_queues.append(queue)

        logger.info(f"[SSEManager] Broadcast {event.event_type} to {success_count} connections for workflow {workflow_id}")

        for queue in disconnected_queues:
            await self.disconnect(workflow_id, queue)

    async def send_event(self, workflow_id: str, event_type: str, data: Any) -> None:
        logger.info(f"[SSEManager] Sending {event_type} event to workflow {workflow_id}")
        event = SSEEvent(event_type=event_type, data=data, workflow_id=workflow_id)
        await self.broadcast(event)

    def get_connection_count(self, workflow_id: str) -> int:
        return len(self._connections.get(workflow_id, set()))


def get_sse_manager() -> SSEConnectionManager:
    return SSEConnectionManager()

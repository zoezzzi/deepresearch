from typing import List, Optional
from dataclasses import asdict
from .event_types import (
    PlanEvent,
    TaskStartEvent,
    TaskCompleteEvent,
    ChunkEvent,
    ResultEvent,
    ErrorEvent
)
from harness.events import get_sse_manager
from harness.logger import logger
from app.common.utils.time_utils import get_current_utc_time


class EventPublisher:
    def __init__(self):
        self.sse_manager = get_sse_manager()

    async def publish_plan_event(
        self,
        workflow_id: str,
        tasks: List[dict]
    ) -> None:
        event = PlanEvent(
            workflow_id=workflow_id,
            tasks=tasks,
            timestamp=get_current_utc_time()
        )
        await self._publish(event)

    async def publish_task_start_event(
        self,
        workflow_id: str,
        task_id: str,
        task_title: str
    ) -> None:
        event = TaskStartEvent(
            workflow_id=workflow_id,
            task_id=task_id,
            task_title=task_title,
            timestamp=get_current_utc_time()
        )
        await self._publish(event)

    async def publish_task_complete_event(
        self,
        workflow_id: str,
        task_id: str,
        task_title: str,
        summary: str,
        sources_summary: str,
        notices: str
    ) -> None:
        event = TaskCompleteEvent(
            workflow_id=workflow_id,
            task_id=task_id,
            task_title=task_title,
            summary=summary,
            sources_summary=sources_summary,
            notices=notices,
            timestamp=get_current_utc_time()
        )
        await self._publish(event)

    async def publish_chunk_event(
        self,
        workflow_id: str,
        content: str
    ) -> None:
        event = ChunkEvent(
            workflow_id=workflow_id,
            content=content,
            timestamp=get_current_utc_time()
        )
        await self._publish(event)

    async def publish_result_event(
        self,
        workflow_id: str,
        report_url: str
    ) -> None:
        event = ResultEvent(
            workflow_id=workflow_id,
            report_url=report_url,
            timestamp=get_current_utc_time()
        )
        await self._publish(event)

    async def publish_error_event(
        self,
        workflow_id: str,
        message: str
    ) -> None:
        event = ErrorEvent(
            workflow_id=workflow_id,
            message=message,
            timestamp=get_current_utc_time()
        )
        await self._publish(event)

    async def _publish(self, event) -> None:
        try:
            event_dict = asdict(event)
            event_type = event_dict.pop("event_type")

            logger.info(f"[EventPublisher] Publishing {event_type} event for workflow {event.workflow_id}")

            await self.sse_manager.send_event(
                workflow_id=event.workflow_id,
                event_type=event_type,
                data=event_dict
            )
            logger.info(f"[EventPublisher] Successfully published {event_type} event for workflow {event.workflow_id}")
        except Exception as e:
            logger.error(f"[EventPublisher] Failed to publish event: {str(e)}")
            import traceback
            logger.error(f"[EventPublisher] Exception traceback: {traceback.format_exc()}")


def get_event_publisher() -> EventPublisher:
    return EventPublisher()

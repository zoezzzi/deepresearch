from datetime import datetime
from typing import Optional
from domain.value_objects.task_status import TaskStatus
from domain.value_objects.task_id import TaskId
from domain.value_objects.workflow_id import WorkflowId
from domain.value_objects.task_intent import TaskIntent
from domain.value_objects.search_query import SearchQuery
from domain.value_objects.task_summary import TaskSummary
from domain.value_objects.sources_summary import SourcesSummary
from domain.value_objects.notices import Notices
from common.utils.time_utils import get_current_utc_time


class Task:
    def __init__(
        self,
        task_id: TaskId,
        workflow_id: WorkflowId,
        title: str,
        intent: TaskIntent,
        query: SearchQuery,
        order: int,
        status: TaskStatus = TaskStatus.PENDING,
        summary: Optional[TaskSummary] = None,
        sources_summary: Optional[SourcesSummary] = None,
        notices: Optional[Notices] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None
    ):
        self.task_id = task_id
        self.workflow_id = workflow_id
        self.title = title
        self.intent = intent
        self.query = query
        self.order = order
        self.status = status
        self.summary = summary
        self.sources_summary = sources_summary
        self.notices = notices
        self.created_at = created_at or get_current_utc_time()
        self.updated_at = updated_at or get_current_utc_time()
        self.started_at = started_at
        self.completed_at = completed_at

    def start(self) -> None:
        self.status = TaskStatus.RUNNING
        self.started_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    def complete(self, summary: TaskSummary, sources_summary: SourcesSummary, notices: Notices) -> None:
        self.status = TaskStatus.COMPLETED
        self.summary = summary
        self.sources_summary = sources_summary
        self.notices = notices
        self.completed_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    def fail(self, error_message: Optional[str] = None) -> None:
        self.status = TaskStatus.FAILED
        self.updated_at = get_current_utc_time()

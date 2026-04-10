from datetime import datetime
from typing import List, Optional
from domain.value_objects.workflow_status import WorkflowStatus
from domain.value_objects.workflow_id import WorkflowId
from domain.value_objects.report_url import ReportUrl
from common.utils.time_utils import get_current_utc_time


class Workflow:
    def __init__(
        self,
        workflow_id: WorkflowId,
        topic: str,
        description: Optional[str] = None,
        status: WorkflowStatus = WorkflowStatus.PENDING,
        report_url: Optional[ReportUrl] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None
    ):
        self.workflow_id = workflow_id
        self.topic = topic
        self.description = description
        self.status = status
        self.report_url = report_url
        self.created_at = created_at or get_current_utc_time()
        self.updated_at = updated_at or get_current_utc_time()
        self.started_at = started_at
        self.completed_at = completed_at
        self._tasks: List = []

    @property
    def tasks(self) -> List:
        return self._tasks

    def add_task(self, task) -> None:
        self._tasks.append(task)
        self.updated_at = get_current_utc_time()

    def start(self) -> None:
        self.status = WorkflowStatus.RUNNING
        self.started_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    def complete(self, report_url: ReportUrl) -> None:
        self.status = WorkflowStatus.COMPLETED
        self.report_url = report_url
        self.completed_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    def fail(self) -> None:
        self.status = WorkflowStatus.FAILED
        self.updated_at = get_current_utc_time()

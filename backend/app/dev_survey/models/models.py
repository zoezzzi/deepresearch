from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.common.utils.time_utils import get_current_utc_time
from app.dev_survey.models.enums import EvaluationStatus, TaskStatus, WorkflowStatus


class InvalidWorkflowStateError(Exception):
    pass


class Task(BaseModel):
    task_id: str
    workflow_id: str
    title: str
    intent: str
    query: str
    order: int
    depends_on: list[str] = Field(default_factory=list)
    status: str = Field(default="pending")
    summary: str | None = None
    sources_summary: str | None = None
    notices: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def model_post_init(self, __context):
        if self.created_at is None:
            self.created_at = get_current_utc_time()
        if self.updated_at is None:
            self.updated_at = get_current_utc_time()

    def start(self) -> None:
        self.status = TaskStatus.RUNNING.value
        self.started_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    def complete(self, summary: str, sources_summary: str, notices: str) -> None:
        self.status = TaskStatus.COMPLETED.value
        self.summary = summary
        self.sources_summary = sources_summary
        self.notices = notices
        self.completed_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    def fail(self, error_message: str | None = None) -> None:
        self.status = TaskStatus.FAILED.value
        self.updated_at = get_current_utc_time()


class Workflow(BaseModel):
    workflow_id: str
    topic: str
    scenario_id: str
    description: str | None = None
    status: str = Field(default="pending")
    report_url: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    tasks: list[Task] = Field(default_factory=list)

    def model_post_init(self, __context):
        if self.created_at is None:
            self.created_at = get_current_utc_time()
        if self.updated_at is None:
            self.updated_at = get_current_utc_time()

    def add_task(self, task: Task) -> None:
        self.tasks.append(task)
        self.updated_at = get_current_utc_time()

    def start(self) -> None:
        if self.status != WorkflowStatus.PENDING.value:
            raise InvalidWorkflowStateError(f"Cannot start workflow from {self.status} status")
        self.status = WorkflowStatus.RUNNING.value
        self.started_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    def mark_all_success(self, report_url: str | None = None) -> None:
        if self.status != WorkflowStatus.RUNNING.value:
            raise InvalidWorkflowStateError(f"Cannot mark all_success from {self.status} status")
        self.status = WorkflowStatus.ALL_SUCCESS.value
        if report_url:
            self.report_url = report_url
        self.completed_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    def mark_partial_failed(self, report_url: str | None = None) -> None:
        if self.status != WorkflowStatus.RUNNING.value:
            raise InvalidWorkflowStateError(f"Cannot mark partial_failed from {self.status} status")
        self.status = WorkflowStatus.PARTIAL_FAILED.value
        if report_url:
            self.report_url = report_url
        self.completed_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    def mark_all_failed(self) -> None:
        if self.status != WorkflowStatus.RUNNING.value:
            raise InvalidWorkflowStateError(f"Cannot mark all_failed from {self.status} status")
        self.status = WorkflowStatus.ALL_FAILED.value
        self.completed_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    def mark_report_failed(self) -> None:
        if self.status != WorkflowStatus.RUNNING.value:
            raise InvalidWorkflowStateError(f"Cannot mark report_failed from {self.status} status")
        self.status = WorkflowStatus.REPORT_FAILED.value
        self.completed_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    def is_terminal(self) -> bool:
        return WorkflowStatus.is_terminal_status(self.status)

    def is_success(self) -> bool:
        return self.status in [
            WorkflowStatus.ALL_SUCCESS.value,
            WorkflowStatus.PARTIAL_FAILED.value,
        ]

    def has_report(self) -> bool:
        return self.report_url is not None

    def get_pending_tasks(self) -> list[Task]:
        return [task for task in self.tasks if task.status == TaskStatus.PENDING.value]

    def get_running_tasks(self) -> list[Task]:
        return [task for task in self.tasks if task.status == TaskStatus.RUNNING.value]

    def get_completed_tasks(self) -> list[Task]:
        return [task for task in self.tasks if task.status == TaskStatus.COMPLETED.value]


class ResearchReport(BaseModel):
    report_id: str
    workflow_id: str
    content: str
    url: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def model_post_init(self, __context):
        if self.created_at is None:
            self.created_at = get_current_utc_time()
        if self.updated_at is None:
            self.updated_at = get_current_utc_time()

    def update_content(self, content: str) -> None:
        self.content = content
        self.updated_at = get_current_utc_time()

    def update_url(self, url: str) -> None:
        self.url = url
        self.updated_at = get_current_utc_time()


class EvaluationResult(BaseModel):
    evaluation_id: str
    workflow_id: str
    scenario_id: str | None = None
    status: str = Field(default="pending")

    # 动态指标存储：支持任意场景的评估指标
    # 失败的指标填充 0.0，确保 metrics 始终包含所有指标
    metrics: dict[str, float] = Field(default_factory=dict)
    overall_score: float | None = None

    error_message: str | None = None
    evaluation_details: dict[str, Any] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def model_post_init(self, __context):
        if self.created_at is None:
            self.created_at = get_current_utc_time()
        if self.updated_at is None:
            self.updated_at = get_current_utc_time()

    def start(self) -> None:
        self.status = EvaluationStatus.IN_PROGRESS.value
        self.started_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    def complete(
        self,
        metrics: dict[str, float],
        overall_score: float,
        evaluation_details: dict[str, Any] | None = None,
    ) -> None:
        self.status = EvaluationStatus.COMPLETED.value
        self.metrics = metrics
        self.overall_score = overall_score
        self.evaluation_details = evaluation_details

        self.completed_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    def fail(self, error_message: str) -> None:
        self.status = EvaluationStatus.FAILED.value
        self.error_message = error_message
        self.completed_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.research_assistant.models.enums import WorkflowStatus, TaskStatus, EvaluationStatus
from app.common.utils.time_utils import get_current_utc_time


class InvalidWorkflowStateError(Exception):
    pass


class Task(BaseModel):
    task_id: str
    workflow_id: str
    title: str
    intent: str
    query: str
    order: int
    status: TaskStatus = TaskStatus.PENDING
    summary: Optional[str] = None
    sources_summary: Optional[str] = None
    notices: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def model_post_init(self, __context):
        if self.created_at is None:
            self.created_at = get_current_utc_time()
        if self.updated_at is None:
            self.updated_at = get_current_utc_time()

    def start(self) -> None:
        self.status = TaskStatus.RUNNING
        self.started_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    def complete(self, summary: str, sources_summary: str, notices: str) -> None:
        self.status = TaskStatus.COMPLETED
        self.summary = summary
        self.sources_summary = sources_summary
        self.notices = notices
        self.completed_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    def fail(self, error_message: Optional[str] = None) -> None:
        self.status = TaskStatus.FAILED
        self.updated_at = get_current_utc_time()


class Workflow(BaseModel):
    workflow_id: str
    topic: str
    scenario_id: str
    description: Optional[str] = None
    status: WorkflowStatus = WorkflowStatus.PENDING
    report_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    tasks: List[Task] = Field(default_factory=list)

    def model_post_init(self, __context):
        if self.created_at is None:
            self.created_at = get_current_utc_time()
        if self.updated_at is None:
            self.updated_at = get_current_utc_time()

    def add_task(self, task: Task) -> None:
        self.tasks.append(task)
        self.updated_at = get_current_utc_time()

    def start(self) -> None:
        if self.status != WorkflowStatus.PENDING:
            raise InvalidWorkflowStateError(
                f"Cannot start workflow from {self.status.value} status"
            )
        self.status = WorkflowStatus.RUNNING
        self.started_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    def mark_all_success(self, report_url: Optional[str] = None) -> None:
        if self.status != WorkflowStatus.RUNNING:
            raise InvalidWorkflowStateError(
                f"Cannot mark all_success from {self.status.value} status"
            )
        self.status = WorkflowStatus.ALL_SUCCESS
        if report_url:
            self.report_url = report_url
        self.completed_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    def mark_partial_failed(self, report_url: Optional[str] = None) -> None:
        if self.status != WorkflowStatus.RUNNING:
            raise InvalidWorkflowStateError(
                f"Cannot mark partial_failed from {self.status.value} status"
            )
        self.status = WorkflowStatus.PARTIAL_FAILED
        if report_url:
            self.report_url = report_url
        self.completed_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    def mark_all_failed(self) -> None:
        if self.status != WorkflowStatus.RUNNING:
            raise InvalidWorkflowStateError(
                f"Cannot mark all_failed from {self.status.value} status"
            )
        self.status = WorkflowStatus.ALL_FAILED
        self.completed_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    def mark_report_failed(self) -> None:
        if self.status != WorkflowStatus.RUNNING:
            raise InvalidWorkflowStateError(
                f"Cannot mark report_failed from {self.status.value} status"
            )
        self.status = WorkflowStatus.REPORT_FAILED
        self.completed_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    def is_terminal(self) -> bool:
        return WorkflowStatus.is_terminal_status(self.status)

    def is_success(self) -> bool:
        return self.status in [
            WorkflowStatus.ALL_SUCCESS,
            WorkflowStatus.PARTIAL_FAILED
        ]

    def has_report(self) -> bool:
        return self.report_url is not None

    def get_pending_tasks(self) -> List[Task]:
        return [task for task in self.tasks if task.status == TaskStatus.PENDING]

    def get_running_tasks(self) -> List[Task]:
        return [task for task in self.tasks if task.status == TaskStatus.RUNNING]

    def get_completed_tasks(self) -> List[Task]:
        return [task for task in self.tasks if task.status == TaskStatus.COMPLETED]


class ResearchReport(BaseModel):
    report_id: str
    workflow_id: str
    content: str
    url: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

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
    scenario_id: Optional[str] = None
    status: EvaluationStatus = EvaluationStatus.PENDING
    
    # 动态指标存储：支持任意场景的评估指标
    # 失败的指标填充 0.0，确保 metrics 始终包含所有指标
    metrics: Dict[str, float] = Field(default_factory=dict)
    overall_score: Optional[float] = None
    
    error_message: Optional[str] = None
    evaluation_details: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def model_post_init(self, __context):
        if self.created_at is None:
            self.created_at = get_current_utc_time()
        if self.updated_at is None:
            self.updated_at = get_current_utc_time()

    def start(self) -> None:
        self.status = EvaluationStatus.IN_PROGRESS
        self.started_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    def complete(
        self,
        metrics: Dict[str, float],
        overall_score: float,
        evaluation_details: Optional[Dict[str, Any]] = None
    ) -> None:
        self.status = EvaluationStatus.COMPLETED
        self.metrics = metrics
        self.overall_score = overall_score
        self.evaluation_details = evaluation_details
        
        self.completed_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    def fail(self, error_message: str) -> None:
        self.status = EvaluationStatus.FAILED
        self.error_message = error_message
        self.completed_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

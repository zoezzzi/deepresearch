from datetime import datetime
from typing import List, Optional
from domain.value_objects.workflow_status import WorkflowStatus
from domain.value_objects.workflow_id import WorkflowId
from domain.value_objects.report_url import ReportUrl
from common.utils.time_utils import get_current_utc_time


class InvalidWorkflowStateError(Exception):
    """工作流状态转换错误"""
    pass


class Workflow:
    """
    工作流实体
    
    职责:
    - 封装工作流的核心属性和行为
    - 管理状态流转
    - 维护任务集合
    
    状态流转:
    - pending → running → [all_success | partial_failed | all_failed | report_failed]
    """
    
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
        """启动工作流"""
        if self.status != WorkflowStatus.PENDING:
            raise InvalidWorkflowStateError(
                f"Cannot start workflow from {self.status.value} status"
            )
        self.status = WorkflowStatus.RUNNING
        self.started_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    # ============ 详细状态转换方法 ============

    def mark_all_success(self, report_url: Optional[ReportUrl] = None) -> None:
        """
        标记工作流全部成功
        
        全部任务成功，报告生成成功
        
        Args:
            report_url: 报告URL
        """
        if self.status != WorkflowStatus.RUNNING:
            raise InvalidWorkflowStateError(
                f"Cannot mark all_success from {self.status.value} status"
            )
        self.status = WorkflowStatus.ALL_SUCCESS
        if report_url:
            self.report_url = report_url
        self.completed_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    def mark_partial_failed(self, report_url: Optional[ReportUrl] = None) -> None:
        """
        标记工作流部分失败
        
        部分任务失败，报告生成成功（或报告也失败）
        
        Args:
            report_url: 报告URL（如果有）
        """
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
        """
        标记工作流全部失败
        
        全部任务失败，不生成报告
        """
        if self.status != WorkflowStatus.RUNNING:
            raise InvalidWorkflowStateError(
                f"Cannot mark all_failed from {self.status.value} status"
            )
        self.status = WorkflowStatus.ALL_FAILED
        self.completed_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    def mark_report_failed(self) -> None:
        """
        标记报告生成失败
        
        全部任务成功，但报告生成失败
        """
        if self.status != WorkflowStatus.RUNNING:
            raise InvalidWorkflowStateError(
                f"Cannot mark report_failed from {self.status.value} status"
            )
        self.status = WorkflowStatus.REPORT_FAILED
        self.completed_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    # ============ 状态查询方法 ============

    def is_terminal(self) -> bool:
        """检查是否为终止状态"""
        return WorkflowStatus.is_terminal_status(self.status)
    
    def is_success(self) -> bool:
        """检查是否成功完成（包括部分失败但有报告的情况）"""
        return self.status in [
            WorkflowStatus.ALL_SUCCESS,
            WorkflowStatus.PARTIAL_FAILED
        ]
    
    def has_report(self) -> bool:
        """检查是否有报告"""
        return self.report_url is not None

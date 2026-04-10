from typing import List, Optional
from domain.entities.workflow import Workflow
from domain.entities.task import Task
from domain.entities.research_report import ResearchReport
from domain.value_objects.workflow_id import WorkflowId
from domain.value_objects.report_url import ReportUrl
from domain.value_objects.workflow_status import WorkflowStatus
from domain.value_objects.task_status import TaskStatus
from common.utils.time_utils import get_current_utc_time


class ResearchWorkflow:
    def __init__(self, workflow: Workflow):
        self.workflow = workflow
        self._report: Optional[ResearchReport] = None

    @property
    def workflow_id(self) -> WorkflowId:
        return self.workflow.workflow_id

    @property
    def tasks(self) -> List[Task]:
        return self.workflow.tasks

    @property
    def report(self) -> Optional[ResearchReport]:
        return self._report

    def add_task(self, task: Task) -> None:
        self.workflow.add_task(task)

    def start(self) -> None:
        self.workflow.start()

    def start_task(self, task_id: str) -> None:
        for task in self.tasks:
            if str(task.task_id) == task_id:
                task.start()
                self.workflow.updated_at = get_current_utc_time()
                return

    def complete_task(self, task_id: str, summary, sources_summary, notices) -> None:
        for task in self.tasks:
            if str(task.task_id) == task_id:
                task.complete(summary, sources_summary, notices)
                self.workflow.updated_at = get_current_utc_time()
                if self._all_tasks_completed():
                    self.workflow.status = WorkflowStatus.COMPLETED
                return

    def fail_task(self, task_id: str) -> None:
        for task in self.tasks:
            if str(task.task_id) == task_id:
                task.fail()
                self.workflow.status = WorkflowStatus.FAILED
                self.workflow.updated_at = get_current_utc_time()
                return

    def _all_tasks_completed(self) -> bool:
        return all(task.status == TaskStatus.COMPLETED for task in self.tasks)

    def complete_workflow(self, report_url: ReportUrl) -> None:
        self.workflow.complete(report_url)

    def fail_workflow(self) -> None:
        self.workflow.fail()

    def attach_report(self, report: ResearchReport) -> None:
        self._report = report

    def get_pending_tasks(self) -> List[Task]:
        return [task for task in self.tasks if task.status == TaskStatus.PENDING]

    def get_running_tasks(self) -> List[Task]:
        return [task for task in self.tasks if task.status == TaskStatus.RUNNING]

    def get_completed_tasks(self) -> List[Task]:
        return [task for task in self.tasks if task.status == TaskStatus.COMPLETED]

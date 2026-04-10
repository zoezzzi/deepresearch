from datetime import datetime
from typing import Optional
from domain.value_objects.workflow_id import WorkflowId
from domain.value_objects.report_content import ReportContent
from domain.value_objects.report_url import ReportUrl
from common.utils.time_utils import get_current_utc_time


class ResearchReport:
    def __init__(
        self,
        report_id: str,
        workflow_id: WorkflowId,
        content: ReportContent,
        url: ReportUrl,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ):
        self.report_id = report_id
        self.workflow_id = workflow_id
        self.content = content
        self.url = url
        self.created_at = created_at or get_current_utc_time()
        self.updated_at = updated_at or get_current_utc_time()

    def update_content(self, content: ReportContent) -> None:
        self.content = content
        self.updated_at = get_current_utc_time()

    def update_url(self, url: ReportUrl) -> None:
        self.url = url
        self.updated_at = get_current_utc_time()

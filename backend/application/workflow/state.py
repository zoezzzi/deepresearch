from typing import TypedDict, List, Optional, Any
from datetime import datetime


class WorkflowState(TypedDict):
    workflow_id: str
    topic: str
    description: Optional[str]
    tasks: List[dict]
    current_task_index: int
    task_results: List[dict]
    report_content: Optional[str]
    report_url: Optional[str]
    error: Optional[str]
    created_at: datetime
    updated_at: datetime

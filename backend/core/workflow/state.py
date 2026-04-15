from typing import TypedDict, List, Optional, Any, Dict
from datetime import datetime


class WorkflowState(TypedDict, total=False):
    workflow_id: str
    topic: str
    description: Optional[str]
    tasks: List[Dict[str, Any]]
    current_task_index: int
    task_results: List[Dict[str, Any]]
    report_content: Optional[str]
    report_url: Optional[str]
    error: Optional[str]
    created_at: datetime
    updated_at: datetime
    workflow_status: Optional[str]
    task_summary: Optional[Dict[str, int]]
    retrieved_chunks: Optional[List[str]]
    sub_questions: Optional[List[str]]
    citations: Optional[List[str]]

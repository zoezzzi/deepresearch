from dataclasses import dataclass
from typing import List, Optional, Any
from datetime import datetime


@dataclass
class PlanEvent:
    workflow_id: str
    tasks: List[dict]
    timestamp: datetime
    event_type: str = "plan"


@dataclass
class TaskStartEvent:
    workflow_id: str
    task_id: str
    task_title: str
    timestamp: datetime
    event_type: str = "task_start"


@dataclass
class TaskCompleteEvent:
    workflow_id: str
    task_id: str
    task_title: str
    summary: str
    sources_summary: str
    notices: str
    timestamp: datetime
    event_type: str = "task_complete"


@dataclass
class ChunkEvent:
    workflow_id: str
    content: str
    timestamp: datetime
    event_type: str = "chunk"


@dataclass
class ResultEvent:
    workflow_id: str
    report_url: str
    timestamp: datetime
    event_type: str = "result"


@dataclass
class ErrorEvent:
    workflow_id: str
    message: str
    timestamp: datetime
    event_type: str = "error"

"""
Trace 仓储接口

定义追踪数据持久化的抽象接口
"""
from abc import ABC, abstractmethod
from typing import Optional, List
from harness.observability.trace_models import (
    WorkflowTraceCreate,
    WorkflowTraceUpdate,
    TaskTraceCreate,
    TaskTraceUpdate,
    WorkflowTraceResponse,
)


class TraceRepository(ABC):
    @abstractmethod
    async def create_workflow_trace(self, trace: WorkflowTraceCreate) -> None:
        pass

    @abstractmethod
    async def update_workflow_trace(self, workflow_id: str, update: WorkflowTraceUpdate) -> None:
        pass

    @abstractmethod
    async def create_task_trace(self, trace: TaskTraceCreate) -> None:
        pass

    @abstractmethod
    async def update_task_trace(self, span_id: str, update: TaskTraceUpdate) -> None:
        pass

    @abstractmethod
    async def get_trace_by_workflow_id(self, workflow_id: str) -> Optional[WorkflowTraceResponse]:
        pass

    @abstractmethod
    async def get_task_traces_by_workflow_id(self, workflow_id: str) -> List:
        pass

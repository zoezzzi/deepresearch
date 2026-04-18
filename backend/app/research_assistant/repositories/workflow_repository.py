from abc import ABC, abstractmethod
from typing import Optional
from app.research_assistant.models.models import Workflow


class WorkflowRepository(ABC):
    @abstractmethod
    async def save(self, workflow: Workflow) -> None:
        pass

    @abstractmethod
    async def find_by_id(self, workflow_id: str) -> Optional[Workflow]:
        pass

    @abstractmethod
    async def update(self, workflow: Workflow) -> None:
        pass

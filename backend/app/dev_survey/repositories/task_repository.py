from abc import ABC, abstractmethod
from typing import List, Optional
from app.dev_survey.models.models import Task


class TaskRepository(ABC):
    @abstractmethod
    async def save(self, task: Task) -> None:
        pass

    @abstractmethod
    async def save_batch(self, tasks: List[Task]) -> None:
        pass

    @abstractmethod
    async def find_by_id(self, task_id: str) -> Optional[Task]:
        pass

    @abstractmethod
    async def find_by_workflow_id(self, workflow_id: str) -> List[Task]:
        pass

    @abstractmethod
    async def update(self, task: Task) -> None:
        pass

    @abstractmethod
    async def update_batch(self, tasks: List[Task]) -> None:
        pass

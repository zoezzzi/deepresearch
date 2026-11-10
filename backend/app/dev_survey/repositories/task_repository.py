from abc import ABC, abstractmethod

from app.dev_survey.models.models import Task


class TaskRepository(ABC):
    @abstractmethod
    async def save(self, task: Task) -> None:
        pass

    @abstractmethod
    async def save_batch(self, tasks: list[Task]) -> None:
        pass

    @abstractmethod
    async def find_by_id(self, task_id: str) -> Task | None:
        pass

    @abstractmethod
    async def find_by_ids(self, task_ids: list[str]) -> list[Task]:
        pass

    @abstractmethod
    async def find_by_workflow_id(self, workflow_id: str) -> list[Task]:
        pass

    @abstractmethod
    async def update(self, task: Task) -> None:
        pass

    @abstractmethod
    async def update_batch(self, tasks: list[Task]) -> None:
        pass

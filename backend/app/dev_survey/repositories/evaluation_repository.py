from abc import ABC, abstractmethod

from app.research_assistant.models.models import EvaluationResult


class EvaluationRepository(ABC):
    @abstractmethod
    async def save(self, evaluation: EvaluationResult) -> None:
        pass

    @abstractmethod
    async def find_by_id(self, evaluation_id: str) -> EvaluationResult | None:
        pass

    @abstractmethod
    async def find_by_workflow_id(self, workflow_id: str) -> list[EvaluationResult]:
        pass

    @abstractmethod
    async def update(self, evaluation: EvaluationResult) -> None:
        pass

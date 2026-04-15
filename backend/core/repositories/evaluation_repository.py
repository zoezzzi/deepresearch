from abc import ABC, abstractmethod
from typing import Optional, List
from core.models import EvaluationResult


class EvaluationRepository(ABC):
    @abstractmethod
    async def save(self, evaluation: EvaluationResult) -> None:
        pass

    @abstractmethod
    async def find_by_id(self, evaluation_id: str) -> Optional[EvaluationResult]:
        pass

    @abstractmethod
    async def find_by_workflow_id(self, workflow_id: str) -> List[EvaluationResult]:
        pass

    @abstractmethod
    async def update(self, evaluation: EvaluationResult) -> None:
        pass

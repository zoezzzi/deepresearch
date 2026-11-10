from abc import ABC, abstractmethod


class BaseEvaluator(ABC):
    @abstractmethod
    async def evaluate(self, **kwargs) -> dict[str, float]:
        pass

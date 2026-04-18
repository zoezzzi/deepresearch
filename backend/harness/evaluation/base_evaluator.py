from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseEvaluator(ABC):
    @abstractmethod
    async def evaluate(self, **kwargs) -> Dict[str, float]:
        pass

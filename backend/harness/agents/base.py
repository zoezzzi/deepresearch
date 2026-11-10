from abc import ABC, abstractmethod
from typing import Any


class Agent(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        pass

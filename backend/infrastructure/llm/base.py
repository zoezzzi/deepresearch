from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Dict, Any


class LLMClient(ABC):
    @abstractmethod
    async def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        pass

    @abstractmethod
    async def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> AsyncGenerator[str, None]:
        pass

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator


class LLMClient(ABC):
    """Abstract LLM client contract.

    Implementations must be safe to call concurrently and should release network
    resources in ``close``.
    """

    @abstractmethod
    async def chat(self, messages: list[dict[str, str]], **kwargs) -> str:
        """Return the assistant reply as plain text."""
        pass

    @abstractmethod
    async def chat_stream(
        self, messages: list[dict[str, str]], **kwargs
    ) -> AsyncGenerator[str, None]:
        """Yield the assistant reply incrementally as text chunks."""
        pass

    async def close(self):
        """释放底层资源，子类可重写以释放连接等"""

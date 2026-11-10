"""Search-source abstraction: a shared result shape and calling contract."""

from abc import ABC, abstractmethod


class SearchResult:
    """Normalized search hit shared by every source implementation."""

    def __init__(self, title: str, url: str, content: str):
        self.title = title
        self.url = url
        self.content = content


class SearchSource(ABC):
    """A pluggable search backend (Tavily, GitHub, Stack Overflow, ...).

    Implementations should be safe for concurrent calls and may hold a shared
    HTTP session; callers must not assume results are de-duplicated.
    """

    @abstractmethod
    async def search(self, query: str, **kwargs) -> list[SearchResult]:
        """Run a query and return normalized results (may be empty)."""
        pass

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class SearchResult:
    def __init__(self, title: str, url: str, content: str):
        self.title = title
        self.url = url
        self.content = content


class SearchSource(ABC):
    @abstractmethod
    async def search(self, query: str, **kwargs) -> List[SearchResult]:
        pass

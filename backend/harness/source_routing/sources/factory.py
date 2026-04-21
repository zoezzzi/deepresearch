from typing import Dict, Type
from harness.source_routing.sources.base import SearchSource
from harness.source_routing.sources.tavily_source import TavilySearchSource
from harness.source_routing.sources.github_source import GitHubSearchSource
from harness.source_routing.sources.stackoverflow_source import StackOverflowSearchSource
from harness.logger import logger


class SearchSourceFactory:
    _sources: Dict[str, Type[SearchSource]] = {
        "tavily": TavilySearchSource,
        "github": GitHubSearchSource,
        "stackoverflow": StackOverflowSearchSource
    }
    
    _source_priority: Dict[str, int] = {
        "github": 3,
        "stackoverflow": 2,
        "tavily": 1
    }

    @classmethod
    def register_source(cls, name: str, source_class: Type[SearchSource], priority: int = 0) -> None:
        cls._sources[name] = source_class
        cls._source_priority[name] = priority
        logger.info(f"Registered search source: {name} (priority: {priority})")

    @classmethod
    def create_source(cls, name: str = "tavily") -> SearchSource:
        if name not in cls._sources:
            raise ValueError(f"Unknown search source: {name}. Available: {list(cls._sources.keys())}")
        logger.debug(f"Creating search source: {name}")
        return cls._sources[name]()
    
    @classmethod
    def get_sources_by_priority(cls) -> list[str]:
        sorted_sources = sorted(
            cls._source_priority.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return [name for name, _ in sorted_sources]


def get_search_source(name: str = "tavily") -> SearchSource:
    return SearchSourceFactory.create_source(name)


def get_sources_by_priority() -> list[str]:
    return SearchSourceFactory.get_sources_by_priority()

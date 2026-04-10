from typing import Dict, Type
from .base import SearchSource
from .tavily_source import TavilySearchSource
from infrastructure.logger import logger


class SearchSourceFactory:
    _sources: Dict[str, Type[SearchSource]] = {
        "tavily": TavilySearchSource
    }

    @classmethod
    def register_source(cls, name: str, source_class: Type[SearchSource]) -> None:
        cls._sources[name] = source_class
        logger.info(f"Registered search source: {name}")

    @classmethod
    def create_source(cls, name: str = "tavily") -> SearchSource:
        if name not in cls._sources:
            raise ValueError(f"Unknown search source: {name}. Available: {list(cls._sources.keys())}")
        logger.info(f"Creating search source: {name}")
        return cls._sources[name]()


def get_search_source(name: str = "tavily") -> SearchSource:
    return SearchSourceFactory.create_source(name)

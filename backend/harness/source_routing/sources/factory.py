"""Search-source factory: create sources by name and expose routing priority."""

from harness.logger import logger
from harness.source_routing.sources.base import SearchSource
from harness.source_routing.sources.github_source import GitHubSearchSource
from harness.source_routing.sources.stackoverflow_source import StackOverflowSearchSource
from harness.source_routing.sources.tavily_source import TavilySearchSource


class SearchSourceFactory:
    """Registry mapping source names to classes, plus routing priority.

    Higher priority values are tried first when the router has no explicit
    preference.
    """

    _sources: dict[str, type[SearchSource]] = {
        "tavily": TavilySearchSource,
        "github": GitHubSearchSource,
        "stackoverflow": StackOverflowSearchSource,
    }

    _source_priority: dict[str, int] = {"github": 3, "stackoverflow": 2, "tavily": 1}

    @classmethod
    def register_source(
        cls, name: str, source_class: type[SearchSource], priority: int = 0
    ) -> None:
        """Register a custom source class and its routing priority."""
        cls._sources[name] = source_class
        cls._source_priority[name] = priority
        logger.info(f"Registered search source: {name} (priority: {priority})")

    @classmethod
    def create_source(cls, name: str = "tavily") -> SearchSource:
        """Instantiate a source by name; raises ValueError when unknown."""
        if name not in cls._sources:
            raise ValueError(
                f"Unknown search source: {name}. Available: {list(cls._sources.keys())}"
            )
        logger.debug(f"Creating search source: {name}")
        return cls._sources[name]()

    @classmethod
    def get_sources_by_priority(cls) -> list[str]:
        """Return source names sorted from highest to lowest priority."""
        sorted_sources = sorted(cls._source_priority.items(), key=lambda x: x[1], reverse=True)
        return [name for name, _ in sorted_sources]


def get_search_source(name: str = "tavily") -> SearchSource:
    return SearchSourceFactory.create_source(name)


def get_sources_by_priority() -> list[str]:
    return SearchSourceFactory.get_sources_by_priority()

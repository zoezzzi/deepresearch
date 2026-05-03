import asyncio
from typing import List, Dict, Any
from tavily import TavilyClient
from tenacity import stop_after_attempt, wait_exponential, retry_if_exception_type
from tenacity import Retrying
from harness.source_routing.sources.base import SearchSource, SearchResult
from harness.config import get_harness_settings
from harness.logger import logger

settings = get_harness_settings()


class TavilySearchSource(SearchSource):
    def __init__(self):
        self.api_key = settings.TAVILY_API_KEY
        self.client = TavilyClient(api_key=self.api_key)
        logger.debug("TavilySearchSource initialized")

    async def search(self, query: str, **kwargs) -> List[SearchResult]:
        max_results = kwargs.get("max_results", 5)
        search_depth = kwargs.get("search_depth", "advanced")
        include_answer = kwargs.get("include_answer", False)

        logger.info(f"Searching Tavily (async via thread pool) for: {query}")

        response = await asyncio.to_thread(
            self._search_sync, query, max_results, search_depth, include_answer
        )

        results = []
        for result in response.get("results", []):
            search_result = SearchResult(
                title=result.get("title", ""),
                url=result.get("url", ""),
                content=result.get("content", "")
            )
            results.append(search_result)

        logger.info(f"Found {len(results)} results from Tavily")
        return results

    def _search_sync(
        self, query: str, max_results: int, search_depth: str, include_answer: bool
    ):
        retrying = Retrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type((ConnectionError,))
        )

        last_attempt = None
        for attempt in retrying:
            with attempt:
                return self.client.search(
                    query=query,
                    search_depth=search_depth,
                    max_results=max_results,
                    include_answer=include_answer
                )
        raise RuntimeError("All Tavily retry attempts exhausted")

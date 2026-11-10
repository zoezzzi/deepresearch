import aiohttp
from tenacity import retry_if_exception_type, stop_after_attempt, wait_exponential
from tenacity.asyncio import AsyncRetrying

from harness.logger import logger
from harness.source_routing.sources.base import SearchResult, SearchSource


class StackOverflowSearchSource(SearchSource):
    """Stack Overflow search source, matching titles and sorting by votes/time.

    Reuses an aiohttp session to avoid repeated TLS handshakes; sessions are not
    shared between instances.
    """

    def __init__(self):
        self.base_url = "https://api.stackexchange.com/2.3"
        self._session: aiohttp.ClientSession | None = None
        logger.debug("StackOverflowSearchSource initialized")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Return a live session, recreating it if it was closed."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(
                limit=10,
                limit_per_host=5,
                ttl_dns_cache=300,
                enable_cleanup_closed=True,
            )
            self._session = aiohttp.ClientSession(connector=connector)
        return self._session

    async def close(self):
        """Close the shared HTTP session if it is still open."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def search(self, query: str, **kwargs) -> list[SearchResult]:
        """Search Stack Overflow and normalize hits.

        Supported kwargs: ``max_results`` (5), ``sort`` ("votes"), ``order``
        ("desc"). Non-200 responses yield an empty list.
        """
        max_results = kwargs.get("max_results", 5)
        sort = kwargs.get("sort", "votes")
        order = kwargs.get("order", "desc")

        retrying = AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type((ConnectionError, aiohttp.ClientError)),
        )

        async for attempt in retrying:
            with attempt:
                logger.info(f"Searching Stack Overflow for: {query}")

                params = {
                    "site": "stackoverflow",
                    "intitle": query,
                    "sort": sort,
                    "order": order,
                    "pagesize": max_results,
                    "filter": "withbody",
                }

                session = await self._get_session()
                url = f"{self.base_url}/search/advanced"

                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        logger.error(f"Stack Overflow API returned status {response.status}")
                        return []

                    data = await response.json()
                    results = []

                    items = data.get("items", [])
                    for item in items[:max_results]:
                        title = item.get("title", "")
                        url = item.get("link", "")
                        score = item.get("score", 0)
                        answer_count = item.get("answer_count", 0)
                        body = item.get("body", "")[:500]

                        content = f"Score: {score}, Answers: {answer_count}\n{body}"

                        search_result = SearchResult(title=title, url=url, content=content)
                        results.append(search_result)

                    logger.info(f"Found {len(results)} results from Stack Overflow")
                    return results

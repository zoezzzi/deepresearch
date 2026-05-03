import aiohttp
from typing import List, Dict, Any, Optional
from tenacity import stop_after_attempt, wait_exponential, retry_if_exception_type
from tenacity.asyncio import AsyncRetrying
from harness.source_routing.sources.base import SearchSource, SearchResult
from harness.config import get_harness_settings
from harness.logger import logger

settings = get_harness_settings()


class GitHubSearchSource(SearchSource):
    def __init__(self):
        self.api_key = getattr(settings, "GITHUB_API_KEY", None)
        self.base_url = "https://api.github.com"
        self._session: Optional[aiohttp.ClientSession] = None
        logger.debug("GitHubSearchSource initialized")

    async def _get_session(self) -> aiohttp.ClientSession:
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
        if self._session and not self._session.closed:
            await self._session.close()

    async def search(self, query: str, **kwargs) -> List[SearchResult]:
        max_results = kwargs.get("max_results", 5)
        search_type = kwargs.get("search_type", "repositories")
        
        retrying = AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type((ConnectionError, aiohttp.ClientError))
        )
        
        async for attempt in retrying:
            with attempt:
                logger.info(f"Searching GitHub for: {query}")
                
                headers = {
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "DeepResearch/1.0"
                }
                if self.api_key:
                    headers["Authorization"] = f"token {self.api_key}"
                
                session = await self._get_session()
                if search_type == "repositories":
                    url = f"{self.base_url}/search/repositories"
                    params = {
                        "q": query,
                        "sort": "stars",
                        "order": "desc",
                        "per_page": max_results
                    }
                elif search_type == "issues":
                    url = f"{self.base_url}/search/issues"
                    params = {
                        "q": query,
                        "sort": "updated",
                        "order": "desc",
                        "per_page": max_results
                    }
                else:
                    url = f"{self.base_url}/search/code"
                    params = {
                        "q": query,
                        "per_page": max_results
                    }
                
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status != 200:
                        logger.error(f"GitHub API returned status {response.status}")
                        return []
                    
                    data = await response.json()
                    results = []
                    
                    items = data.get("items", [])
                    for item in items[:max_results]:
                        if search_type == "repositories":
                            title = item.get("name", "")
                            url = item.get("html_url", "")
                            description = item.get("description", "")
                            stars = item.get("stargazers_count", 0)
                            forks = item.get("forks_count", 0)
                            content = f"{description}\nStars: {stars}, Forks: {forks}"
                        elif search_type == "issues":
                            title = item.get("title", "")
                            url = item.get("html_url", "")
                            content = item.get("body", "")[:500]
                        else:
                            title = item.get("name", "")
                            url = item.get("html_url", "")
                            content = item.get("repository", {}).get("full_name", "")
                        
                        search_result = SearchResult(
                            title=title,
                            url=url,
                            content=content
                        )
                        results.append(search_result)
                    
                    logger.info(f"Found {len(results)} results from GitHub")
                    return results

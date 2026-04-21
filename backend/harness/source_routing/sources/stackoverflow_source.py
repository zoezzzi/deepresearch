from typing import List, Dict, Any
import aiohttp
from tenacity import stop_after_attempt, wait_exponential, retry_if_exception_type
from tenacity.asyncio import AsyncRetrying
from harness.source_routing.sources.base import SearchSource, SearchResult
from harness.logger import logger


class StackOverflowSearchSource(SearchSource):
    def __init__(self):
        self.base_url = "https://api.stackexchange.com/2.3"
        logger.debug("StackOverflowSearchSource initialized")

    async def search(self, query: str, **kwargs) -> List[SearchResult]:
        max_results = kwargs.get("max_results", 5)
        sort = kwargs.get("sort", "votes")
        order = kwargs.get("order", "desc")
        
        retrying = AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type((ConnectionError, aiohttp.ClientError))
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
                    "filter": "withbody"
                }
                
                async with aiohttp.ClientSession() as session:
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
                            
                            search_result = SearchResult(
                                title=title,
                                url=url,
                                content=content
                            )
                            results.append(search_result)
                        
                        logger.info(f"Found {len(results)} results from Stack Overflow")
                        return results

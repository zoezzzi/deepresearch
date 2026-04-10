from typing import List
from .base import Agent
from domain.value_objects.search_query import SearchQuery
from infrastructure.logger import logger


class SearchAgent(Agent):
    def __init__(self, search_source):
        super().__init__("SearchAgent")
        self.search_source = search_source

    async def execute(self, query: SearchQuery) -> List:
        logger.info(f"[{self.name}] Searching for: {query.value}")
        
        try:
            results = await self.search_source.search(query.value)
            logger.info(f"[{self.name}] Found {len(results)} search results")
            return results
        except Exception as e:
            logger.error(f"[{self.name}] Search failed: {str(e)}")
            raise

from typing import List
from harness.agents.base import Agent
from harness.logger import logger


class SearchAgent(Agent):
    def __init__(self, search_source):
        super().__init__("SearchAgent")
        self.search_source = search_source

    async def execute(self, query: str) -> List:
        logger.info(f"[{self.name}] Searching for: {query}")

        try:
            results = await self.search_source.search(query)
            logger.info(f"[{self.name}] Found {len(results)} search results")
            return results
        except Exception as e:
            logger.error(f"[{self.name}] Search failed: {str(e)}")
            raise

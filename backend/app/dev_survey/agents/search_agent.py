from typing import List
from harness.agents.base import Agent
from harness.source_routing.sources.factory import get_search_source, get_sources_by_priority
from harness.logger import logger


class SearchAgent(Agent):
    def __init__(self):
        super().__init__("SearchAgent")
        self.sources = []
        for source_name in get_sources_by_priority():
            try:
                source = get_search_source(source_name)
                self.sources.append(source)
                logger.info(f"[{self.name}] Registered search source: {source_name}")
            except Exception as e:
                logger.warning(f"[{self.name}] Failed to register search source {source_name}: {e}")

    async def execute(self, query: str) -> List:
        logger.info(f"[{self.name}] Searching for: {query}")
        
        all_results = []
        for source in self.sources:
            try:
                source_name = source.__class__.__name__
                logger.info(f"[{self.name}] Searching with {source_name}...")
                results = await source.search(query, max_results=3)
                all_results.extend(results)
                logger.info(f"[{self.name}] Got {len(results)} results from {source_name}")
            except Exception as e:
                logger.warning(f"[{self.name}] Search failed with {source.__class__.__name__}: {str(e)}")
                continue
        
        logger.info(f"[{self.name}] Found total {len(all_results)} search results from all sources")
        return all_results

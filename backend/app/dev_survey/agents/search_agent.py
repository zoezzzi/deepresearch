import asyncio
from typing import List
from harness.agents.base import Agent
from harness.source_routing.sources.factory import get_search_source, get_sources_by_priority
from harness.logger import logger

INTENT_SOURCE_MAP = {
    "对比": ["github", "tavily"],
    "架构": ["github", "tavily"],
    "实现": ["github", "tavily"],
    "选型": ["tavily", "github"],
    "陷阱": ["stackoverflow", "tavily"],
    "踩坑": ["stackoverflow", "tavily"],
    "问题": ["stackoverflow", "tavily"],
    "错误": ["stackoverflow", "tavily"],
    "最佳实践": ["tavily", "github"],
    "性能": ["tavily", "github"],
    "安全": ["tavily", "stackoverflow"],
}


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

    async def execute(self, query: str, intent: str = "") -> List:
        logger.info(f"[{self.name}] Searching for: {query}, intent: {intent}")

        selected_sources = self._select_sources(intent)
        queries = self._generate_search_queries(query, intent)

        search_semaphore = asyncio.Semaphore(10)

        async def search_one(q: str, src):
            async with search_semaphore:
                try:
                    source_name = src.__class__.__name__
                    logger.info(f"[{self.name}] Searching with {source_name} for: {q}")
                    results = await src.search(q, max_results=3)
                    logger.info(f"[{self.name}] Got {len(results)} results from {source_name}")
                    return results
                except Exception as e:
                    logger.warning(f"[{self.name}] Search failed with {src.__class__.__name__}: {str(e)}")
                    return []

        coroutines = [
            search_one(q, src)
            for q in queries
            for src in selected_sources
        ]

        results_per_pair = await asyncio.gather(*coroutines, return_exceptions=True)

        all_results = []
        seen_urls = set()
        for results in results_per_pair:
            if isinstance(results, Exception):
                continue
            for r in results:
                if r.url not in seen_urls:
                    seen_urls.add(r.url)
                    all_results.append(r)

        logger.info(f"[{self.name}] Found total {len(all_results)} search results")

        return all_results

    def _select_sources(self, intent: str) -> list:
        if not intent:
            return self.sources

        preferred_names = set()
        for keyword, source_names in INTENT_SOURCE_MAP.items():
            if keyword in intent:
                preferred_names.update(source_names)

        if not preferred_names:
            return self.sources

        selected = [
            s for s in self.sources
            if s.__class__.__name__.replace("SearchSource", "").lower() in preferred_names
        ]
        return selected if selected else self.sources

    def _generate_search_queries(self, query: str, intent: str) -> List[str]:
        queries = [query]

        if any(kw in intent for kw in ["对比", "vs", "选型"]):
            queries.append(f"{query} comparison vs alternatives")
        if any(kw in intent for kw in ["陷阱", "踩坑", "问题", "错误"]):
            queries.append(f"{query} common issues problems pitfalls")
        if any(kw in intent for kw in ["架构", "实现", "最佳实践"]):
            queries.append(f"{query} architecture implementation best practices")

        return queries[:3]

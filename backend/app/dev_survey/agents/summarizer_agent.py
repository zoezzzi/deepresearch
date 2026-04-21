from typing import List, Dict, Any, Tuple
from harness.agents.base import Agent
from harness.agents.template_renderer import TemplateRenderer
from harness.config import get_harness_settings
from harness.logger import logger
from app.dev_survey.prompts.summarizer_agent_prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

settings = get_harness_settings()


class SummarizerAgent(Agent):
    def __init__(self, llm_client):
        super().__init__("SummarizerAgent")
        self.llm_client = llm_client
        self.timeout = settings.LLM_TIMEOUT_EXECUTE

    async def execute(self, intent: str, search_results: List) -> Tuple[str, str, str]:
        logger.info(f"[{self.name}] Summarizing search results for intent: {intent}")

        try:
            formatted_results = "\n\n".join([
                f"Source {i+1}:\nTitle: {result.title}\nURL: {result.url}\nContent: {result.content[:500]}..."
                for i, result in enumerate(search_results[:5])
            ])

            renderer = TemplateRenderer()
            prompt = renderer.render(USER_PROMPT_TEMPLATE, intent=intent, formatted_results=formatted_results)

            response = await self.llm_client.chat([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ], timeout=self.timeout)

            summary, sources_summary, notices = self._parse_response(response, search_results)
            logger.info(f"[{self.name}] Successfully summarized results")
            return summary, sources_summary, notices
        except Exception as e:
            logger.error(f"[{self.name}] Summarization failed: {str(e)}")
            raise

    def _parse_response(self, response: str, search_results: List) -> Tuple[str, str, str]:
        lines = response.split('\n')
        summary_parts = []
        sources_parts = []
        notices_parts = []

        current_section = None

        for line in lines:
            line_lower = line.lower()
            if 'technical summary' in line_lower:
                current_section = 'summary'
            elif 'sources summary' in line_lower:
                current_section = 'sources'
            elif 'pitfalls' in line_lower or 'warnings' in line_lower or 'best practices' in line_lower:
                current_section = 'notices'
            elif current_section == 'summary':
                summary_parts.append(line)
            elif current_section == 'sources':
                sources_parts.append(line)
            elif current_section == 'notices':
                notices_parts.append(line)

        if not sources_parts:
            sources_parts = [f"- {result.title}: {result.url}" for result in search_results[:5]]

        summary_text = '\n'.join(summary_parts).strip() or response[:500]
        sources_text = '\n'.join(sources_parts).strip()
        notices_text = '\n'.join(notices_parts).strip()

        if not sources_text:
            sources_text = "No sources available"
        if not notices_text:
            notices_text = "No notices"

        return summary_text, sources_text, notices_text

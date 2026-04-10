from typing import List, Dict, Any, Tuple
from .base import Agent
from domain.value_objects.task_intent import TaskIntent
from domain.value_objects.task_summary import TaskSummary
from domain.value_objects.sources_summary import SourcesSummary
from domain.value_objects.notices import Notices
from infrastructure.logger import logger


class SummarizerAgent(Agent):
    def __init__(self, llm_client):
        super().__init__("SummarizerAgent")
        self.llm_client = llm_client

    async def execute(self, intent: TaskIntent, search_results: List) -> Tuple[TaskSummary, SourcesSummary, Notices]:
        logger.info(f"[{self.name}] Summarizing search results for intent: {intent.value}")
        
        try:
            prompt = self._build_prompt(intent, search_results)
            
            response = await self.llm_client.chat([
                {"role": "system", "content": "You are a research summarization expert. Provide clear, concise summaries of research findings."},
                {"role": "user", "content": prompt}
            ])
            
            summary, sources_summary, notices = self._parse_response(response, search_results)
            logger.info(f"[{self.name}] Successfully summarized results")
            return summary, sources_summary, notices
        except Exception as e:
            logger.error(f"[{self.name}] Summarization failed: {str(e)}")
            raise

    def _build_prompt(self, intent: TaskIntent, search_results: List) -> str:
        formatted_results = "\n\n".join([
            f"Source {i+1}:\nTitle: {result.title}\nURL: {result.url}\nContent: {result.content[:500]}..."
            for i, result in enumerate(search_results[:5])
        ])
        
        return f"""Research Intent: {intent.value}

Search Results:
{formatted_results}

Please provide:
1. A comprehensive summary of the findings related to the intent
2. A summary of the sources used (with URLs)
3. Any important notices or caveats about the information

Format your response clearly with these three sections."""

    def _parse_response(self, response: str, search_results: List) -> Tuple[TaskSummary, SourcesSummary, Notices]:
        lines = response.split('\n')
        summary_parts = []
        sources_parts = []
        notices_parts = []
        
        current_section = None
        
        for line in lines:
            line_lower = line.lower()
            if 'summary' in line_lower and 'finding' in line_lower:
                current_section = 'summary'
            elif 'source' in line_lower:
                current_section = 'sources'
            elif 'notice' in line_lower or 'caveat' in line_lower:
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
        
        return (
            TaskSummary(summary_text),
            SourcesSummary(sources_text),
            Notices(notices_text)
        )

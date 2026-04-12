from typing import List
from .base import Agent
from domain.entities.task import Task
from domain.value_objects.report_content import ReportContent
from common.logger import logger


class GenerateAgent(Agent):
    def __init__(self, llm_client):
        super().__init__("GenerateAgent")
        self.llm_client = llm_client

    async def execute(self, topic: str, tasks: List[Task]) -> ReportContent:
        logger.info(f"[{self.name}] Generating research report for topic: {topic}")
        
        try:
            prompt = self._build_prompt(topic, tasks)
            
            response = await self.llm_client.chat([
                {"role": "system", "content": "You are a research report generation expert. Create comprehensive, well-structured research reports in Markdown format."},
                {"role": "user", "content": prompt}
            ])
            
            report_content = ReportContent(response)
            logger.info(f"[{self.name}] Successfully generated research report")
            return report_content
        except Exception as e:
            logger.error(f"[{self.name}] Report generation failed: {str(e)}")
            raise

    def _build_prompt(self, topic: str, tasks: List[Task]) -> str:
        task_summaries = []
        for task in sorted(tasks, key=lambda t: t.order):
            intent = task.intent.value if task.intent else "No intent"
            summary = task.summary.value if task.summary else "No summary"
            sources = task.sources_summary.value if task.sources_summary else "No sources"
            notices = task.notices.value if task.notices else "No notices"
            
            task_summaries.append(f"""
## Task {task.order}: {task.title}
**Intent:** {intent}
**Summary:** {summary}
**Sources:** {sources}
**Notices:** {notices}
""")
        
        return f"""Generate a comprehensive research report on the following topic:

Topic: {topic}

Research Task Summaries:
{"".join(task_summaries)}

Please create a well-structured Markdown report that includes:
1. Title page with topic
2. Table of contents
3. Executive summary
4. Main findings organized by sections
5. Conclusion
6. References section with all sources

Make the report professional, comprehensive, and easy to read."""

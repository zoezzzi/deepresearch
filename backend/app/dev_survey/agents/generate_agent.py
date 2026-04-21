import asyncio
from typing import List
from harness.agents.base import Agent
from harness.agents.template_renderer import TemplateRenderer
from harness.config import get_harness_settings
from harness.logger import logger
from app.dev_survey.models.models import Task
from app.dev_survey.prompts.generate_agent_prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

settings = get_harness_settings()


class GenerateAgent(Agent):
    def __init__(self, llm_client):
        super().__init__("GenerateAgent")
        self.llm_client = llm_client
        self.timeout = settings.LLM_TIMEOUT_REPORT

    async def execute(self, topic: str, tasks: List[Task]) -> str:
        logger.info(f"[{self.name}] Generating research report for topic: {topic}")

        try:
            task_summaries = []
            for task in sorted(tasks, key=lambda t: t.order):
                intent = task.intent or "No intent"
                summary = task.summary or "No summary"
                sources = task.sources_summary or "No sources"
                notices = task.notices or "No notices"

                task_summaries.append(f"""
## Task {task.order}: {task.title}
**Intent:** {intent}
**Summary:** {summary}
**Sources:** {sources}
**Notices:** {notices}
""")

            renderer = TemplateRenderer()
            prompt = renderer.render(USER_PROMPT_TEMPLATE, topic=topic, task_summaries="".join(task_summaries))

            logger.info(f"[{self.name}] Attempting to generate report with timeout: {self.timeout}s")
            try:
                response = await self.llm_client.chat(
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt}
                    ],
                    timeout=self.timeout
                )

                logger.info(f"[{self.name}] Successfully generated research report")
                return response
            except Exception as e:
                logger.warning(f"[{self.name}] Report generation failed, trying simplified report: {str(e)}")
                return await self._generate_simplified_report(topic, tasks)

        except Exception as e:
            logger.error(f"[{self.name}] Report generation failed: {str(e)}")
            raise

    async def _generate_simplified_report(self, topic: str, tasks: List[Task]) -> str:
        """生成简化版本的报告（降级策略）"""
        logger.info(f"[{self.name}] Generating simplified report for topic: {topic}")

        try:
            # 简单的报告模板，只包含任务摘要
            report_parts = [f"# {topic}", "", "## 任务总结", ""]

            for task in sorted(tasks, key=lambda t: t.order):
                if hasattr(task, "status") and task.status == "completed":
                    report_parts.append(f"### {task.title}")
                    if task.summary:
                        report_parts.append(f"{task.summary[:200]}...")  # 只取前200字符
                    else:
                        report_parts.append("No summary available")
                    report_parts.append("")

            report_parts.append("---")
            report_parts.append("*Note: This is a simplified version due to report generation timeout.*")

            return "\n".join(report_parts)
        except Exception as e:
            logger.error(f"[{self.name}] Simplified report generation also failed: {str(e)}")
            # 返回最基本的报告
            completed_count = len([t for t in tasks if hasattr(t, "status") and t.status == "completed"])
            return f"# {topic}\n\nReport generation failed. {completed_count} tasks completed successfully."

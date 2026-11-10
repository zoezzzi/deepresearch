import asyncio

from app.research_assistant.models.models import Task
from harness.agents.base import Agent
from harness.logger import logger


class GenerateAgent(Agent):
    def __init__(self, llm_client):
        super().__init__("GenerateAgent")
        self.llm_client = llm_client

    async def execute(self, topic: str, tasks: list[Task]) -> str:
        logger.info(f"[{self.name}] Generating research report for topic: {topic}")

        try:
            prompt = self._build_prompt(topic, tasks)

            # 添加重试机制
            max_attempts = 3
            last_error = None

            for attempt in range(max_attempts):
                try:
                    logger.info(
                        f"[{self.name}] Attempt {attempt + 1}/{max_attempts} to generate report"
                    )
                    response = await self.llm_client.chat(
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a research report generation expert. Create comprehensive, well-structured research reports in Markdown format.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        timeout=600,  # 10 分钟超时，报告生成需要更多时间
                    )

                    logger.info(f"[{self.name}] Successfully generated research report")
                    return response
                except Exception as e:
                    last_error = e
                    logger.warning(f"[{self.name}] Attempt {attempt + 1} failed: {str(e)}")
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(5)  # 短暂延迟后重试
                    else:
                        # 最后一次失败，尝试生成简化报告
                        logger.warning(
                            f"[{self.name}] All attempts failed, trying simplified report"
                        )
                        return await self._generate_simplified_report(topic, tasks)

            logger.error(f"[{self.name}] All {max_attempts} attempts failed: {str(last_error)}")
            raise Exception(
                f"Report generation failed after {max_attempts} attempts: {str(last_error)}"
            )

        except Exception as e:
            logger.error(f"[{self.name}] Report generation failed: {str(e)}")
            raise

    async def _generate_simplified_report(self, topic: str, tasks: list[Task]) -> str:
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
            report_parts.append(
                "*Note: This is a simplified version due to report generation timeout.*"
            )

            return "\n".join(report_parts)
        except Exception as e:
            logger.error(f"[{self.name}] Simplified report generation also failed: {str(e)}")
            # 返回最基本的报告
            completed_count = len(
                [t for t in tasks if hasattr(t, "status") and t.status == "completed"]
            )
            return f"# {topic}\n\nReport generation failed. {completed_count} tasks completed successfully."

    def _build_prompt(self, topic: str, tasks: list[Task]) -> str:
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

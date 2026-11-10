from app.dev_survey.models.models import Task
from app.dev_survey.prompts.generate_agent_prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from app.dev_survey.validators.report_validator import ReportValidator
from harness.agents.base import Agent
from harness.agents.template_renderer import TemplateRenderer
from harness.config import get_harness_settings
from harness.logger import logger

settings = get_harness_settings()


class GenerateAgent(Agent):
    def __init__(self, llm_client):
        super().__init__("GenerateAgent")
        self.llm_client = llm_client
        self.timeout = settings.LLM_TIMEOUT_REPORT

    async def execute(self, topic: str, tasks: list[Task]) -> str:
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

            available_sources = self._collect_sources(tasks)

            renderer = TemplateRenderer()
            prompt = renderer.render(
                USER_PROMPT_TEMPLATE,
                topic=topic,
                task_summaries="".join(task_summaries),
                available_sources=available_sources,
            )

            logger.info(
                f"[{self.name}] Attempting to generate report with timeout: {self.timeout}s"
            )
            try:
                current_report = await self.llm_client.chat(
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    timeout=self.timeout,
                )

                logger.info(f"[{self.name}] Successfully generated research report")

                max_tries = getattr(settings, "MAX_REPORT_SELF_CHECK_TRIES", 1)
                validator = ReportValidator()

                for attempt in range(max_tries):
                    is_valid, missing_sections = validator.validate(current_report)
                    if is_valid:
                        logger.info(
                            f"[{self.name}] Report validation passed on attempt {attempt + 1}"
                        )
                        break

                    logger.warning(
                        f"[{self.name}] Report missing sections on attempt {attempt + 1}: {missing_sections}, generating supplement"
                    )
                    supplement = await self._generate_supplement(
                        topic, current_report, missing_sections
                    )
                    current_report = self._merge_supplement(current_report, supplement)

                return current_report
            except Exception as e:
                logger.warning(
                    f"[{self.name}] Report generation failed, trying simplified report: {str(e)}"
                )
                return await self._generate_simplified_report(topic, tasks)

        except Exception as e:
            logger.error(f"[{self.name}] Report generation failed: {str(e)}")
            raise

    def _collect_sources(self, tasks: list[Task]) -> str:
        sources = []
        seen_urls = set()

        for task in sorted(tasks, key=lambda t: t.order):
            if task.sources_summary:
                for line in task.sources_summary.split("\n"):
                    line = line.strip()
                    if line.startswith("- ") or line.startswith("* "):
                        line = line[2:]
                    for url_pattern in ["http://", "https://"]:
                        idx = line.find(url_pattern)
                        if idx != -1:
                            url = line[idx:].split()[0].rstrip(")")
                            if url not in seen_urls:
                                seen_urls.add(url)
                                sources.append(f"[{len(sources) + 1}] {line}")
                                break

        if not sources:
            return "No specific sources available for citation."

        return "\n".join(sources)

    async def _generate_supplement(
        self, topic: str, report: str, missing_sections: list[str]
    ) -> str:
        sections_text = "、".join(missing_sections)
        prompt = (
            f"以下技术调研报告缺少必要章节：{sections_text}。"
            f"请补充这些章节的内容。报告主题：{topic}\n\n"
            f"已有报告内容（摘要）：\n{report[:1000]}\n\n"
            f"请直接输出补充的章节内容（Markdown格式）："
        )

        try:
            response = await self.llm_client.chat(
                [{"role": "user", "content": prompt}], timeout=self.timeout
            )
            return response
        except Exception:
            logger.error(f"[{self.name}] Supplement generation failed")
            return ""

    def _merge_supplement(self, report: str, supplement: str) -> str:
        if not supplement:
            return report
        return report + "\n\n" + supplement

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

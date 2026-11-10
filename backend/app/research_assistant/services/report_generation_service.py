import uuid

from app.research_assistant.agents import GenerateAgent
from app.research_assistant.models.models import ResearchReport, Task
from harness.logger import logger


class ReportGenerationService:
    def __init__(self, generate_agent: GenerateAgent):
        self.generate_agent = generate_agent

    async def generate_report(
        self, workflow_id: str, topic: str, tasks: list[Task]
    ) -> ResearchReport:
        logger.info(f"[ReportGenerationService] Generating report for workflow: {workflow_id}")

        try:
            report_content = await self.generate_agent.execute(topic, tasks)

            report_id = str(uuid.uuid4())
            report_url = f"/reports/{report_id}"

            report = ResearchReport(
                report_id=report_id, workflow_id=workflow_id, content=report_content, url=report_url
            )

            logger.info(f"[ReportGenerationService] Report generated successfully: {report_id}")
            return report
        except Exception as e:
            logger.error(f"[ReportGenerationService] Failed to generate report: {str(e)}")
            raise

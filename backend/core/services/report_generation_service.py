from typing import List
import uuid
from core.agents import GenerateAgent
from core.models import Task, ResearchReport
from common.logger import logger


class ReportGenerationService:
    def __init__(self, generate_agent: GenerateAgent):
        self.generate_agent = generate_agent

    async def generate_report(
        self,
        workflow_id: str,
        topic: str,
        tasks: List[Task]
    ) -> ResearchReport:
        logger.info(f"[ReportGenerationService] Generating report for workflow: {workflow_id}")

        try:
            report_content = await self.generate_agent.execute(topic, tasks)

            report_id = str(uuid.uuid4())
            report_url = f"/reports/{report_id}"

            report = ResearchReport(
                report_id=report_id,
                workflow_id=workflow_id,
                content=report_content,
                url=report_url
            )

            logger.info(f"[ReportGenerationService] Report generated successfully: {report_id}")
            return report
        except Exception as e:
            logger.error(f"[ReportGenerationService] Failed to generate report: {str(e)}")
            raise

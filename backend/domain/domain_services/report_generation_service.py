from typing import List
import uuid
from domain.agents.generate_agent import GenerateAgent
from domain.entities.task import Task
from domain.entities.research_report import ResearchReport
from domain.value_objects.workflow_id import WorkflowId
from domain.value_objects.report_content import ReportContent
from domain.value_objects.report_url import ReportUrl
from infrastructure.logger import logger


class ReportGenerationService:
    def __init__(self, generate_agent: GenerateAgent):
        self.generate_agent = generate_agent

    async def generate_report(
        self,
        workflow_id: WorkflowId,
        topic: str,
        tasks: List[Task]
    ) -> ResearchReport:
        logger.info(f"[ReportGenerationService] Generating report for workflow: {workflow_id.value}")
        
        try:
            report_content = await self.generate_agent.execute(topic, tasks)
            
            report_id = str(uuid.uuid4())
            report_url = ReportUrl(f"/reports/{report_id}")
            
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

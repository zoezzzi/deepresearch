"""
ReportGenerationService 测试
"""
import pytest
from unittest.mock import AsyncMock
from core.services.report_generation_service import ReportGenerationService
from core.models import Task


class TestReportGenerationService:
    """ReportGenerationService 测试"""

    @pytest.fixture
    def generate_agent(self, mock_llm_client):
        """创建 GenerateAgent fixture"""
        from core.agents import GenerateAgent
        return GenerateAgent(mock_llm_client)

    @pytest.fixture
    def report_generation_service(self, generate_agent):
        """创建 ReportGenerationService fixture"""
        return ReportGenerationService(generate_agent)

    @pytest.fixture
    def sample_tasks(self, sample_workflow_id):
        """创建示例任务列表"""
        return [
            Task(
                task_id="task-1",
                workflow_id=sample_workflow_id,
                title="Task 1",
                intent="Intent 1",
                query="query 1",
                order=1
            ),
            Task(
                task_id="task-2",
                workflow_id=sample_workflow_id,
                title="Task 2",
                intent="Intent 2",
                query="query 2",
                order=2
            )
        ]

    @pytest.mark.asyncio
    async def test_generate_report_success(self, report_generation_service, mock_llm_client, sample_workflow_id, sample_tasks):
        """验证报告生成成功"""
        mock_llm_client.chat.return_value = "# Test Report\n\nThis is a test report."
        
        report = await report_generation_service.generate_report(
            workflow_id=sample_workflow_id,
            topic="Test Topic",
            tasks=sample_tasks
        )
        
        assert report is not None
        assert report.workflow_id == sample_workflow_id
        assert report.content == "# Test Report\n\nThis is a test report."
        assert report.url is not None

    @pytest.mark.asyncio
    async def test_generate_report_calls_llm(self, report_generation_service, mock_llm_client, sample_workflow_id, sample_tasks):
        """验证报告生成调用 LLM"""
        mock_llm_client.chat.return_value = "Report content"
        
        await report_generation_service.generate_report(
            workflow_id=sample_workflow_id,
            topic="Test Topic",
            tasks=sample_tasks
        )
        
        mock_llm_client.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_report_error_handling(self, report_generation_service, mock_llm_client, sample_workflow_id, sample_tasks):
        """验证报告生成错误处理"""
        mock_llm_client.chat.side_effect = Exception("LLM Error")
        
        with pytest.raises(Exception, match="LLM Error"):
            await report_generation_service.generate_report(
                workflow_id=sample_workflow_id,
                topic="Test Topic",
                tasks=sample_tasks
            )

"""
ResearchService 功能测试
测试研究服务的完整流程
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.services.research_service import ResearchService
from core.models import Workflow, WorkflowStatus, CreateResearchRequest


class TestResearchServiceFunctional:
    """ResearchService 功能测试"""

    @pytest.fixture
    def research_service(
        self,
        mock_workflow_repository,
        mock_task_repository,
        mock_evaluation_repository,
        mock_llm_client,
        mock_search_source,
        mock_event_publisher,
        mock_object_storage,
        mock_evaluation_orchestrator
    ):
        """创建 ResearchService fixture"""
        with patch('core.services.research_service.get_llm_client', return_value=mock_llm_client), \
             patch('core.services.research_service.get_search_source', return_value=mock_search_source), \
             patch('core.services.research_service.get_event_publisher', return_value=mock_event_publisher), \
             patch('core.services.research_service.LocalObjectStorage', return_value=mock_object_storage):
            
            from core.services import EvaluationService
            evaluation_service = EvaluationService(mock_evaluation_repository)
            
            return ResearchService(
                workflow_repository=mock_workflow_repository,
                task_repository=mock_task_repository,
                evaluation_service=evaluation_service,
                evaluation_orchestrator=mock_evaluation_orchestrator
            )

    @pytest.mark.asyncio
    async def test_create_research_workflow(self, research_service, mock_workflow_repository):
        """验证创建调研工作流"""
        request = CreateResearchRequest(topic="Test Topic", description="Test Description")
        
        response = await research_service.create_research_workflow(request)
        
        assert response is not None
        assert response.topic == "Test Topic"
        assert response.description == "Test Description"
        assert response.status == WorkflowStatus.PENDING
        mock_workflow_repository.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_workflow_status(self, research_service, mock_workflow_repository, sample_workflow_id):
        """验证获取工作流状态"""
        workflow = Workflow(
            workflow_id=sample_workflow_id,
            topic="Test Topic",
            status=WorkflowStatus.PENDING
        )
        mock_workflow_repository.find_by_id.return_value = workflow
        
        response = await research_service.get_workflow_status(sample_workflow_id)
        
        assert response is not None
        assert response.workflow_id == sample_workflow_id
        assert response.topic == "Test Topic"

    @pytest.mark.asyncio
    async def test_get_workflow_status_not_found(self, research_service, mock_workflow_repository, sample_workflow_id):
        """验证获取不存在的工作流状态"""
        mock_workflow_repository.find_by_id.return_value = None
        
        with pytest.raises(ValueError, match="Workflow not found"):
            await research_service.get_workflow_status(sample_workflow_id)

    @pytest.mark.asyncio
    async def test_get_report_content(self, research_service, mock_workflow_repository, mock_object_storage, sample_workflow_id):
        """验证获取报告内容"""
        workflow = Workflow(
            workflow_id=sample_workflow_id,
            topic="Test Topic",
            status=WorkflowStatus.ALL_SUCCESS,
            report_url="/reports/test-report.md"
        )
        mock_workflow_repository.find_by_id.return_value = workflow
        mock_object_storage.read_file.return_value = "# Test Report"
        
        content = await research_service.get_report_content(sample_workflow_id)
        
        assert content == "# Test Report"

    @pytest.mark.asyncio
    async def test_get_report_content_no_report(self, research_service, mock_workflow_repository, sample_workflow_id):
        """验证获取报告内容时无报告"""
        workflow = Workflow(
            workflow_id=sample_workflow_id,
            topic="Test Topic",
            status=WorkflowStatus.PENDING
        )
        mock_workflow_repository.find_by_id.return_value = workflow
        
        content = await research_service.get_report_content(sample_workflow_id)
        
        assert content is None

    @pytest.mark.asyncio
    async def test_to_workflow_response(self, research_service, sample_workflow):
        """验证工作流响应转换"""
        response = research_service._to_workflow_response(sample_workflow)
        
        assert response.workflow_id == sample_workflow.workflow_id
        assert response.topic == sample_workflow.topic
        assert response.status == sample_workflow.status

    @pytest.mark.asyncio
    async def test_to_task_response(self, research_service, sample_task):
        """验证任务响应转换"""
        response = research_service._to_task_response(sample_task)
        
        assert response.task_id == sample_task.task_id
        assert response.title == sample_task.title
        assert response.status == "pending"


class TestWorkflowStateTransitions:
    """工作流状态转换功能测试"""

    def test_workflow_pending_to_running(self, sample_workflow):
        """验证从 PENDING 到 RUNNING 的状态转换"""
        sample_workflow.start()
        assert sample_workflow.status == WorkflowStatus.RUNNING

    def test_workflow_running_to_all_success(self, sample_workflow):
        """验证从 RUNNING 到 ALL_SUCCESS 的状态转换"""
        sample_workflow.start()
        sample_workflow.mark_all_success("/reports/test")
        assert sample_workflow.status == WorkflowStatus.ALL_SUCCESS

    def test_workflow_running_to_partial_failed(self, sample_workflow):
        """验证从 RUNNING 到 PARTIAL_FAILED 的状态转换"""
        sample_workflow.start()
        sample_workflow.mark_partial_failed("/reports/test")
        assert sample_workflow.status == WorkflowStatus.PARTIAL_FAILED

    def test_workflow_running_to_all_failed(self, sample_workflow):
        """验证从 RUNNING 到 ALL_FAILED 的状态转换"""
        sample_workflow.start()
        sample_workflow.mark_all_failed()
        assert sample_workflow.status == WorkflowStatus.ALL_FAILED

    def test_workflow_running_to_report_failed(self, sample_workflow):
        """验证从 RUNNING 到 REPORT_FAILED 的状态转换"""
        sample_workflow.start()
        sample_workflow.mark_report_failed()
        assert sample_workflow.status == WorkflowStatus.REPORT_FAILED


class TestTaskLifecycle:
    """任务生命周期功能测试"""

    def test_task_pending_to_running(self, sample_task):
        """验证任务从 PENDING 到 RUNNING"""
        sample_task.start()
        assert sample_task.status.value == "running"

    def test_task_running_to_completed(self, sample_task):
        """验证任务从 RUNNING 到 COMPLETED"""
        sample_task.start()
        sample_task.complete("summary", "sources", "notices")
        assert sample_task.status.value == "completed"
        assert sample_task.summary == "summary"

    def test_task_running_to_failed(self, sample_task):
        """验证任务从 RUNNING 到 FAILED"""
        sample_task.start()
        sample_task.fail("error message")
        assert sample_task.status.value == "failed"

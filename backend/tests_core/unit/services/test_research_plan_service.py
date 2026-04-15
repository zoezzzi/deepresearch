"""
ResearchPlanService 测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from core.services.research_plan_service import ResearchPlanService
from core.models import Task, TaskStatus


class TestResearchPlanService:
    """ResearchPlanService 测试"""

    @pytest.fixture
    def plan_agent(self, mock_llm_client):
        """创建 PlanAgent fixture"""
        from core.agents import PlanAgent
        return PlanAgent(mock_llm_client)

    @pytest.fixture
    def research_plan_service(self, plan_agent):
        """创建 ResearchPlanService fixture"""
        return ResearchPlanService(plan_agent)

    @pytest.mark.asyncio
    async def test_generate_tasks_success(self, research_plan_service, mock_llm_client, sample_workflow_id):
        """验证任务生成成功"""
        mock_llm_client.chat.return_value = '''
        [
            {"title": "Task 1", "intent": "Intent 1", "query": "query 1", "order": 1},
            {"title": "Task 2", "intent": "Intent 2", "query": "query 2", "order": 2}
        ]
        '''
        
        tasks = await research_plan_service.generate_tasks(
            workflow_id=sample_workflow_id,
            topic="Test Topic"
        )
        
        assert len(tasks) == 2
        assert all(isinstance(task, Task) for task in tasks)
        assert tasks[0].title == "Task 1"
        assert tasks[1].title == "Task 2"
        assert tasks[0].workflow_id == sample_workflow_id
        assert tasks[0].status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_generate_tasks_with_description(self, research_plan_service, mock_llm_client, sample_workflow_id):
        """验证带描述的任务生成"""
        mock_llm_client.chat.return_value = '''
        [{"title": "Task 1", "intent": "Intent 1", "query": "query 1", "order": 1}]
        '''
        
        tasks = await research_plan_service.generate_tasks(
            workflow_id=sample_workflow_id,
            topic="Test Topic",
            description="Test Description"
        )
        
        assert len(tasks) == 1
        mock_llm_client.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_tasks_missing_fields(self, research_plan_service, mock_llm_client, sample_workflow_id):
        """验证缺少字段时使用默认值"""
        mock_llm_client.chat.return_value = '''
        [{"title": "Task 1"}]
        '''
        
        tasks = await research_plan_service.generate_tasks(
            workflow_id=sample_workflow_id,
            topic="Test Topic"
        )
        
        assert len(tasks) == 1
        assert tasks[0].title == "Task 1"
        assert tasks[0].intent == "Research about Test Topic"
        assert tasks[0].query == "Test Topic"
        assert tasks[0].order == 1

    @pytest.mark.asyncio
    async def test_generate_tasks_error_handling(self, research_plan_service, mock_llm_client, sample_workflow_id):
        """验证错误处理"""
        mock_llm_client.chat.side_effect = Exception("LLM Error")
        
        with pytest.raises(Exception, match="LLM Error"):
            await research_plan_service.generate_tasks(
                workflow_id=sample_workflow_id,
                topic="Test Topic"
            )

    @pytest.mark.asyncio
    async def test_generate_tasks_auto_order(self, research_plan_service, mock_llm_client, sample_workflow_id):
        """验证自动排序"""
        mock_llm_client.chat.return_value = '''
        [
            {"title": "Task 1", "intent": "Intent 1", "query": "query 1"},
            {"title": "Task 2", "intent": "Intent 2", "query": "query 2"}
        ]
        '''
        
        tasks = await research_plan_service.generate_tasks(
            workflow_id=sample_workflow_id,
            topic="Test Topic"
        )
        
        assert tasks[0].order == 1
        assert tasks[1].order == 2

"""
ResearchWorkflowGraph 测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.workflow.graph import ResearchWorkflowGraph
from core.workflow.state import WorkflowState


class TestResearchWorkflowGraph:
    """ResearchWorkflowGraph 测试"""

    @pytest.fixture
    def workflow_graph(
        self,
        mock_llm_client,
        mock_search_source,
        mock_task_repository,
        mock_event_publisher,
        mock_object_storage,
        mock_evaluation_repository,
        mock_evaluation_orchestrator
    ):
        """创建 ResearchWorkflowGraph fixture"""
        from core.agents import PlanAgent, SearchAgent, SummarizerAgent, GenerateAgent
        from core.services import ResearchPlanService, TaskExecutionService, ReportGenerationService, EvaluationService
        
        plan_agent = PlanAgent(mock_llm_client)
        search_agent = SearchAgent(mock_search_source)
        summarizer_agent = SummarizerAgent(mock_llm_client)
        generate_agent = GenerateAgent(mock_llm_client)
        
        research_plan_service = ResearchPlanService(plan_agent)
        task_execution_service = TaskExecutionService(search_agent, summarizer_agent)
        report_generation_service = ReportGenerationService(generate_agent)
        evaluation_service = EvaluationService(mock_evaluation_repository)
        
        return ResearchWorkflowGraph(
            research_plan_service=research_plan_service,
            task_execution_service=task_execution_service,
            report_generation_service=report_generation_service,
            event_publisher=mock_event_publisher,
            task_repository=mock_task_repository,
            object_storage=mock_object_storage,
            evaluation_service=evaluation_service,
            evaluation_orchestrator=mock_evaluation_orchestrator
        )

    def test_workflow_graph_creation(self, workflow_graph):
        """验证工作流图创建"""
        assert workflow_graph is not None
        assert workflow_graph.graph is not None

    def test_workflow_graph_has_plan_node(self, workflow_graph):
        """验证工作流图包含计划节点"""
        assert hasattr(workflow_graph, '_plan_node')

    def test_workflow_graph_has_execute_task_node(self, workflow_graph):
        """验证工作流图包含执行任务节点"""
        assert hasattr(workflow_graph, '_execute_task_node')

    def test_workflow_graph_has_generate_report_node(self, workflow_graph):
        """验证工作流图包含生成报告节点"""
        assert hasattr(workflow_graph, '_generate_report_node')

    def test_workflow_graph_has_should_continue(self, workflow_graph):
        """验证工作流图包含继续判断方法"""
        assert hasattr(workflow_graph, '_should_continue')

    @pytest.mark.asyncio
    async def test_plan_node_creates_tasks(self, workflow_graph, mock_llm_client, mock_task_repository):
        """验证计划节点创建任务"""
        mock_llm_client.chat.return_value = '''
        [{"title": "Task 1", "intent": "Intent 1", "query": "query 1", "order": 1}]
        '''
        
        state: WorkflowState = {
            "workflow_id": "test-workflow",
            "topic": "Test Topic",
            "description": "",
            "tasks": [],
            "current_task_index": 0,
            "task_results": [],
            "created_at": None,
            "updated_at": None
        }
        
        result = await workflow_graph._plan_node(state)
        
        assert "tasks" in result
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["title"] == "Task 1"

    def test_should_continue_with_error(self, workflow_graph):
        """验证错误时继续到生成报告"""
        state: WorkflowState = {
            "workflow_id": "test-workflow",
            "topic": "Test Topic",
            "tasks": [],
            "current_task_index": 0,
            "task_results": [],
            "error": "Some error",
            "created_at": None,
            "updated_at": None
        }
        
        result = workflow_graph._should_continue(state)
        assert result == "generate_report"

    def test_should_continue_all_tasks_done(self, workflow_graph):
        """验证所有任务完成后继续到生成报告"""
        state: WorkflowState = {
            "workflow_id": "test-workflow",
            "topic": "Test Topic",
            "tasks": [
                {"task_id": "task-1", "status": "completed"}
            ],
            "current_task_index": 1,
            "task_results": [],
            "created_at": None,
            "updated_at": None
        }
        
        result = workflow_graph._should_continue(state)
        assert result == "generate_report"

    def test_should_continue_more_tasks(self, workflow_graph):
        """验证还有更多任务时继续执行"""
        state: WorkflowState = {
            "workflow_id": "test-workflow",
            "topic": "Test Topic",
            "tasks": [
                {"task_id": "task-1", "status": "completed"},
                {"task_id": "task-2", "status": "pending"}
            ],
            "current_task_index": 0,
            "task_results": [],
            "created_at": None,
            "updated_at": None
        }
        
        result = workflow_graph._should_continue(state)
        assert result == "continue"

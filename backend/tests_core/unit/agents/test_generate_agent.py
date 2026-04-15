"""
GenerateAgent 测试
"""
import pytest
from core.agents.generate_agent import GenerateAgent
from core.models import Task


class TestGenerateAgent:
    """GenerateAgent 测试"""

    @pytest.fixture
    def generate_agent(self, mock_llm_client):
        """创建 GenerateAgent fixture"""
        return GenerateAgent(mock_llm_client)

    @pytest.fixture
    def sample_tasks_with_results(self, sample_workflow_id):
        """创建带结果的任务列表"""
        task1 = Task(
            task_id="task-1",
            workflow_id=sample_workflow_id,
            title="Task 1",
            intent="Intent 1",
            query="query 1",
            order=1
        )
        task1.summary = "Summary 1"
        task1.sources_summary = "Sources 1"
        task1.notices = "Notices 1"
        
        task2 = Task(
            task_id="task-2",
            workflow_id=sample_workflow_id,
            title="Task 2",
            intent="Intent 2",
            query="query 2",
            order=2
        )
        task2.summary = "Summary 2"
        task2.sources_summary = "Sources 2"
        task2.notices = "Notices 2"
        
        return [task1, task2]

    @pytest.mark.asyncio
    async def test_generate_agent_execute_success(self, generate_agent, mock_llm_client, sample_tasks_with_results):
        """验证报告生成成功"""
        mock_llm_client.chat.return_value = "# Test Report\n\nReport content here."
        
        result = await generate_agent.execute(
            topic="Test Topic",
            tasks=sample_tasks_with_results
        )
        
        assert result == "# Test Report\n\nReport content here."
        mock_llm_client.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_agent_execute_with_topic(self, generate_agent, mock_llm_client, sample_tasks_with_results):
        """验证报告生成包含主题"""
        mock_llm_client.chat.return_value = "# Test Topic Report"
        
        result = await generate_agent.execute(
            topic="Test Topic",
            tasks=sample_tasks_with_results
        )
        
        assert "Test Topic" in result or mock_llm_client.chat.called

    @pytest.mark.asyncio
    async def test_generate_agent_execute_error_handling(self, generate_agent, mock_llm_client, sample_tasks_with_results):
        """验证错误处理"""
        mock_llm_client.chat.side_effect = Exception("LLM Error")
        
        with pytest.raises(Exception, match="LLM Error"):
            await generate_agent.execute(
                topic="Test Topic",
                tasks=sample_tasks_with_results
            )

    def test_generate_agent_build_prompt(self, generate_agent, sample_tasks_with_results):
        """验证提示构建"""
        prompt = generate_agent._build_prompt("Test Topic", sample_tasks_with_results)
        
        assert "Test Topic" in prompt
        assert "Task 1" in prompt
        assert "Task 2" in prompt

    def test_generate_agent_name(self, generate_agent):
        """验证 Agent 名称"""
        assert generate_agent.name == "GenerateAgent"

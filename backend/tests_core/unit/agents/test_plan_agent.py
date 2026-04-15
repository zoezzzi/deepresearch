"""
PlanAgent 测试
"""
import pytest
import json
from core.agents.plan_agent import PlanAgent


class TestPlanAgent:
    """PlanAgent 测试"""

    @pytest.fixture
    def plan_agent(self, mock_llm_client):
        """创建 PlanAgent fixture"""
        return PlanAgent(mock_llm_client)

    @pytest.mark.asyncio
    async def test_plan_agent_execute_success(self, plan_agent, mock_llm_client):
        """验证计划生成成功"""
        mock_response = json.dumps([
            {"title": "Task 1", "intent": "Intent 1", "query": "query 1", "order": 1},
            {"title": "Task 2", "intent": "Intent 2", "query": "query 2", "order": 2}
        ])
        mock_llm_client.chat.return_value = mock_response
        
        result = await plan_agent.execute(topic="Test Topic")
        
        assert len(result) == 2
        assert result[0]["title"] == "Task 1"
        assert result[1]["title"] == "Task 2"

    @pytest.mark.asyncio
    async def test_plan_agent_execute_with_description(self, plan_agent, mock_llm_client):
        """验证带描述的计划生成"""
        mock_llm_client.chat.return_value = '[{"title": "Task 1", "intent": "Intent 1", "query": "query 1", "order": 1}]'
        
        result = await plan_agent.execute(topic="Test Topic", description="Test Description")
        
        assert len(result) == 1
        mock_llm_client.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_plan_agent_parse_response_valid_json(self, plan_agent):
        """验证有效 JSON 响应解析"""
        response = '''
        Some text before
        [
            {"title": "Task 1", "intent": "Intent 1", "query": "query 1", "order": 1}
        ]
        Some text after
        '''
        
        result = plan_agent._parse_response(response, "Test Topic")
        
        assert len(result) == 1
        assert result[0]["title"] == "Task 1"

    @pytest.mark.asyncio
    async def test_plan_agent_parse_response_invalid_json(self, plan_agent):
        """验证无效 JSON 响应使用默认值"""
        response = "This is not valid JSON"
        
        result = plan_agent._parse_response(response, "Test Topic")
        
        assert len(result) == 1
        assert "Test Topic" in result[0]["title"]

    @pytest.mark.asyncio
    async def test_plan_agent_execute_error_handling(self, plan_agent, mock_llm_client):
        """验证错误处理"""
        mock_llm_client.chat.side_effect = Exception("LLM Error")
        
        with pytest.raises(Exception, match="LLM Error"):
            await plan_agent.execute(topic="Test Topic")

    def test_plan_agent_build_prompt(self, plan_agent):
        """验证提示构建"""
        prompt = plan_agent._build_prompt("Test Topic", "Test Description")
        
        assert "Test Topic" in prompt
        assert "Test Description" in prompt

"""
SearchAgent 测试
"""
import pytest
from core.agents.search_agent import SearchAgent


class TestSearchAgent:
    """SearchAgent 测试"""

    @pytest.fixture
    def search_agent(self, mock_search_source):
        """创建 SearchAgent fixture"""
        return SearchAgent(mock_search_source)

    @pytest.mark.asyncio
    async def test_search_agent_execute_success(self, search_agent, mock_search_source):
        """验证搜索执行成功"""
        results = await search_agent.execute(query="test query")
        
        assert len(results) == 1
        assert results[0].title == "Test Result"
        mock_search_source.search.assert_called_once_with("test query")

    @pytest.mark.asyncio
    async def test_search_agent_execute_empty_results(self, search_agent, mock_search_source):
        """验证空搜索结果"""
        mock_search_source.search.return_value = []
        
        results = await search_agent.execute(query="test query")
        
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_agent_execute_error_handling(self, search_agent, mock_search_source):
        """验证错误处理"""
        mock_search_source.search.side_effect = Exception("Search Error")
        
        with pytest.raises(Exception, match="Search Error"):
            await search_agent.execute(query="test query")

    def test_search_agent_name(self, search_agent):
        """验证 Agent 名称"""
        assert search_agent.name == "SearchAgent"

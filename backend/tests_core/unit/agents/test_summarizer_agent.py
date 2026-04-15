"""
SummarizerAgent 测试
"""
import pytest
from unittest.mock import MagicMock
from core.agents.summarizer_agent import SummarizerAgent


class TestSummarizerAgent:
    """SummarizerAgent 测试"""

    @pytest.fixture
    def summarizer_agent(self, mock_llm_client):
        """创建 SummarizerAgent fixture"""
        return SummarizerAgent(mock_llm_client)

    @pytest.fixture
    def mock_search_results(self):
        """创建模拟搜索结果"""
        result = MagicMock()
        result.title = "Test Result"
        result.url = "https://example.com"
        result.content = "Test content for summarization"
        return [result]

    @pytest.mark.asyncio
    async def test_summarizer_agent_execute_success(self, summarizer_agent, mock_llm_client, mock_search_results):
        """验证摘要生成成功"""
        mock_llm_client.chat.return_value = """
        Summary: This is a test summary.
        Sources: https://example.com
        Notices: No notices.
        """
        
        summary, sources, notices = await summarizer_agent.execute(
            intent="Test intent",
            search_results=mock_search_results
        )
        
        assert summary is not None
        assert sources is not None
        assert notices is not None

    @pytest.mark.asyncio
    async def test_summarizer_agent_execute_calls_llm(self, summarizer_agent, mock_llm_client, mock_search_results):
        """验证摘要生成调用 LLM"""
        mock_llm_client.chat.return_value = "Summary content"
        
        await summarizer_agent.execute(
            intent="Test intent",
            search_results=mock_search_results
        )
        
        mock_llm_client.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_summarizer_agent_execute_error_handling(self, summarizer_agent, mock_llm_client, mock_search_results):
        """验证错误处理"""
        mock_llm_client.chat.side_effect = Exception("LLM Error")
        
        with pytest.raises(Exception, match="LLM Error"):
            await summarizer_agent.execute(
                intent="Test intent",
                search_results=mock_search_results
            )

    def test_summarizer_agent_build_prompt(self, summarizer_agent, mock_search_results):
        """验证提示构建"""
        prompt = summarizer_agent._build_prompt("Test intent", mock_search_results)
        
        assert "Test intent" in prompt
        assert "Test Result" in prompt

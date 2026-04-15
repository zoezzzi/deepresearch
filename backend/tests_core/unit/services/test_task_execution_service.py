"""
TaskExecutionService 测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from core.services.task_execution_service import TaskExecutionService
from core.models import Task


class TestTaskExecutionService:
    """TaskExecutionService 测试"""

    @pytest.fixture
    def search_agent(self, mock_search_source):
        """创建 SearchAgent fixture"""
        from core.agents import SearchAgent
        return SearchAgent(mock_search_source)

    @pytest.fixture
    def summarizer_agent(self, mock_llm_client):
        """创建 SummarizerAgent fixture"""
        from core.agents import SummarizerAgent
        return SummarizerAgent(mock_llm_client)

    @pytest.fixture
    def task_execution_service(self, search_agent, summarizer_agent):
        """创建 TaskExecutionService fixture"""
        return TaskExecutionService(search_agent, summarizer_agent)

    @pytest.mark.asyncio
    async def test_execute_task_success(self, task_execution_service, sample_task, mock_llm_client):
        """验证任务执行成功"""
        mock_llm_client.chat.return_value = """
        Summary: Test summary
        Sources: Test sources
        Notices: Test notices
        """
        
        summary, sources_summary, notices = await task_execution_service.execute_task(sample_task)
        
        assert summary is not None
        assert sources_summary is not None
        assert notices is not None

    @pytest.mark.asyncio
    async def test_execute_task_calls_search(self, task_execution_service, sample_task, mock_search_source, mock_llm_client):
        """验证任务执行调用搜索"""
        mock_llm_client.chat.return_value = "Summary content"
        
        await task_execution_service.execute_task(sample_task)
        
        mock_search_source.search.assert_called_once_with(sample_task.query)

    @pytest.mark.asyncio
    async def test_execute_task_error_handling(self, task_execution_service, sample_task, mock_search_source):
        """验证任务执行错误处理"""
        mock_search_source.search.side_effect = Exception("Search Error")
        
        with pytest.raises(Exception, match="Search Error"):
            await task_execution_service.execute_task(sample_task)

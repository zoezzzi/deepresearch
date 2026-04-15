"""
EventPublisher 测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from core.events.event_publisher import EventPublisher
from core.events.event_types import PlanEvent, TaskStartEvent, TaskCompleteEvent


class TestEventPublisher:
    """EventPublisher 测试"""

    @pytest.fixture
    def mock_sse_manager(self):
        """创建模拟 SSE 管理器"""
        manager = AsyncMock()
        manager.send_event = AsyncMock()
        return manager

    @pytest.fixture
    def event_publisher(self, mock_sse_manager):
        """创建 EventPublisher fixture"""
        with patch('core.events.event_publisher.get_sse_manager', return_value=mock_sse_manager):
            return EventPublisher()

    @pytest.mark.asyncio
    async def test_publish_plan_event(self, event_publisher, mock_sse_manager):
        """验证发布计划事件"""
        await event_publisher.publish_plan_event(
            workflow_id="test-workflow",
            tasks=[{"task_id": "task-1", "title": "Task 1"}]
        )
        
        mock_sse_manager.send_event.assert_called_once()
        call_args = mock_sse_manager.send_event.call_args
        assert call_args[1]["workflow_id"] == "test-workflow"
        assert call_args[1]["event_type"] == "plan"

    @pytest.mark.asyncio
    async def test_publish_task_start_event(self, event_publisher, mock_sse_manager):
        """验证发布任务开始事件"""
        await event_publisher.publish_task_start_event(
            workflow_id="test-workflow",
            task_id="task-1",
            task_title="Test Task"
        )
        
        mock_sse_manager.send_event.assert_called_once()
        call_args = mock_sse_manager.send_event.call_args
        assert call_args[1]["event_type"] == "task_start"

    @pytest.mark.asyncio
    async def test_publish_task_complete_event(self, event_publisher, mock_sse_manager):
        """验证发布任务完成事件"""
        await event_publisher.publish_task_complete_event(
            workflow_id="test-workflow",
            task_id="task-1",
            task_title="Test Task",
            summary="Test summary",
            sources_summary="Test sources",
            notices="Test notices"
        )
        
        mock_sse_manager.send_event.assert_called_once()
        call_args = mock_sse_manager.send_event.call_args
        assert call_args[1]["event_type"] == "task_complete"

    @pytest.mark.asyncio
    async def test_publish_result_event(self, event_publisher, mock_sse_manager):
        """验证发布结果事件"""
        await event_publisher.publish_result_event(
            workflow_id="test-workflow",
            report_url="/reports/test-report.md"
        )
        
        mock_sse_manager.send_event.assert_called_once()
        call_args = mock_sse_manager.send_event.call_args
        assert call_args[1]["event_type"] == "result"

    @pytest.mark.asyncio
    async def test_publish_error_event(self, event_publisher, mock_sse_manager):
        """验证发布错误事件"""
        await event_publisher.publish_error_event(
            workflow_id="test-workflow",
            message="Test error message"
        )
        
        mock_sse_manager.send_event.assert_called_once()
        call_args = mock_sse_manager.send_event.call_args
        assert call_args[1]["event_type"] == "error"

    @pytest.mark.asyncio
    async def test_publish_event_handles_exception(self, event_publisher, mock_sse_manager):
        """验证事件发布异常处理"""
        mock_sse_manager.send_event.side_effect = Exception("SSE Error")
        
        await event_publisher.publish_plan_event(
            workflow_id="test-workflow",
            tasks=[]
        )

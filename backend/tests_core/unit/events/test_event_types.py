"""
Event Types 测试
"""
import pytest
from datetime import datetime
from core.events.event_types import (
    PlanEvent,
    TaskStartEvent,
    TaskCompleteEvent,
    ChunkEvent,
    ResultEvent,
    ErrorEvent
)


class TestPlanEvent:
    """PlanEvent 测试"""

    def test_plan_event_creation(self):
        """验证计划事件创建"""
        event = PlanEvent(
            workflow_id="test-workflow",
            tasks=[{"task_id": "task-1", "title": "Task 1"}],
            timestamp=datetime.now()
        )
        
        assert event.workflow_id == "test-workflow"
        assert len(event.tasks) == 1
        assert event.event_type == "plan"

    def test_plan_event_has_timestamp(self):
        """验证计划事件有时间戳"""
        event = PlanEvent(
            workflow_id="test-workflow",
            tasks=[],
            timestamp=datetime.now()
        )
        
        assert event.timestamp is not None


class TestTaskStartEvent:
    """TaskStartEvent 测试"""

    def test_task_start_event_creation(self):
        """验证任务开始事件创建"""
        event = TaskStartEvent(
            workflow_id="test-workflow",
            task_id="task-1",
            task_title="Test Task",
            timestamp=datetime.now()
        )
        
        assert event.workflow_id == "test-workflow"
        assert event.task_id == "task-1"
        assert event.task_title == "Test Task"
        assert event.event_type == "task_start"


class TestTaskCompleteEvent:
    """TaskCompleteEvent 测试"""

    def test_task_complete_event_creation(self):
        """验证任务完成事件创建"""
        event = TaskCompleteEvent(
            workflow_id="test-workflow",
            task_id="task-1",
            task_title="Test Task",
            summary="Test summary",
            sources_summary="Test sources",
            notices="Test notices",
            timestamp=datetime.now()
        )
        
        assert event.workflow_id == "test-workflow"
        assert event.task_id == "task-1"
        assert event.summary == "Test summary"
        assert event.sources_summary == "Test sources"
        assert event.notices == "Test notices"
        assert event.event_type == "task_complete"


class TestChunkEvent:
    """ChunkEvent 测试"""

    def test_chunk_event_creation(self):
        """验证块事件创建"""
        event = ChunkEvent(
            workflow_id="test-workflow",
            content="Test chunk content",
            timestamp=datetime.now()
        )
        
        assert event.workflow_id == "test-workflow"
        assert event.content == "Test chunk content"
        assert event.event_type == "chunk"


class TestResultEvent:
    """ResultEvent 测试"""

    def test_result_event_creation(self):
        """验证结果事件创建"""
        event = ResultEvent(
            workflow_id="test-workflow",
            report_url="/reports/test-report.md",
            timestamp=datetime.now()
        )
        
        assert event.workflow_id == "test-workflow"
        assert event.report_url == "/reports/test-report.md"
        assert event.event_type == "result"


class TestErrorEvent:
    """ErrorEvent 测试"""

    def test_error_event_creation(self):
        """验证错误事件创建"""
        event = ErrorEvent(
            workflow_id="test-workflow",
            message="Something went wrong",
            timestamp=datetime.now()
        )
        
        assert event.workflow_id == "test-workflow"
        assert event.message == "Something went wrong"
        assert event.event_type == "error"

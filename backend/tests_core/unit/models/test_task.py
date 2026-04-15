"""
Task 模型测试
测试 Task 数据模型的行为
"""
import pytest
from datetime import datetime
from core.models import Task, TaskStatus


class TestTaskCreation:
    """Task 创建测试"""

    def test_task_creation_basic(self, sample_task_id, sample_workflow_id):
        """验证 Task 基本创建"""
        task = Task(
            task_id=sample_task_id,
            workflow_id=sample_workflow_id,
            title="Test Task",
            intent="Test intent",
            query="test query",
            order=1
        )
        
        assert task.task_id == sample_task_id
        assert task.workflow_id == sample_workflow_id
        assert task.title == "Test Task"
        assert task.intent == "Test intent"
        assert task.query == "test query"
        assert task.order == 1
        assert task.status == TaskStatus.PENDING

    def test_task_creation_with_auto_timestamp(self, sample_task_id, sample_workflow_id):
        """验证 Task 自动生成时间戳"""
        task = Task(
            task_id=sample_task_id,
            workflow_id=sample_workflow_id,
            title="Test Task",
            intent="Test intent",
            query="test query",
            order=1
        )
        
        assert task.created_at is not None
        assert task.updated_at is not None
        assert isinstance(task.created_at, datetime)
        assert isinstance(task.updated_at, datetime)

    def test_task_creation_with_explicit_timestamp(self, sample_task_id, sample_workflow_id):
        """验证 Task 显式时间戳"""
        explicit_time = datetime(2024, 1, 1, 12, 0, 0)
        task = Task(
            task_id=sample_task_id,
            workflow_id=sample_workflow_id,
            title="Test Task",
            intent="Test intent",
            query="test query",
            order=1,
            created_at=explicit_time,
            updated_at=explicit_time
        )
        
        assert task.created_at == explicit_time
        assert task.updated_at == explicit_time

    def test_task_creation_default_optional_fields(self, sample_task):
        """验证 Task 可选字段默认值"""
        assert sample_task.summary is None
        assert sample_task.sources_summary is None
        assert sample_task.notices is None
        assert sample_task.started_at is None
        assert sample_task.completed_at is None


class TestTaskStatusTransitions:
    """Task 状态转换测试"""

    def test_task_start(self, sample_task):
        """验证任务启动"""
        sample_task.start()
        
        assert sample_task.status == TaskStatus.RUNNING
        assert sample_task.started_at is not None
        assert sample_task.updated_at is not None

    def test_task_complete(self, sample_task):
        """验证任务完成"""
        sample_task.start()
        sample_task.complete(
            summary="Test summary",
            sources_summary="Test sources",
            notices="Test notices"
        )
        
        assert sample_task.status == TaskStatus.COMPLETED
        assert sample_task.summary == "Test summary"
        assert sample_task.sources_summary == "Test sources"
        assert sample_task.notices == "Test notices"
        assert sample_task.completed_at is not None

    def test_task_fail(self, sample_task):
        """验证任务失败"""
        sample_task.start()
        sample_task.fail("Test error message")
        
        assert sample_task.status == TaskStatus.FAILED
        assert sample_task.updated_at is not None

    def test_task_fail_without_error_message(self, sample_task):
        """验证任务失败不需要错误消息"""
        sample_task.start()
        sample_task.fail()
        
        assert sample_task.status == TaskStatus.FAILED


class TestTaskSerialization:
    """Task 序列化测试"""

    def test_task_model_dump(self, sample_task):
        """验证 Task 模型转字典"""
        data = sample_task.model_dump()
        
        assert data["task_id"] == sample_task.task_id
        assert data["workflow_id"] == sample_task.workflow_id
        assert data["title"] == sample_task.title
        assert data["status"] == TaskStatus.PENDING

    def test_task_model_json(self, sample_task):
        """验证 Task 模型转 JSON"""
        json_str = sample_task.model_dump_json()
        
        assert sample_task.task_id in json_str
        assert sample_task.title in json_str

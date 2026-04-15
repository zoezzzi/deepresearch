"""
Workflow 模型测试
测试 Workflow 数据模型的行为
"""
import pytest
from core.models import Workflow, Task, WorkflowStatus, TaskStatus, InvalidWorkflowStateError


class TestWorkflowCreation:
    """Workflow 创建测试"""

    def test_workflow_creation_basic(self, sample_workflow_id):
        """验证 Workflow 基本创建"""
        workflow = Workflow(
            workflow_id=sample_workflow_id,
            topic="Test Topic"
        )
        
        assert workflow.workflow_id == sample_workflow_id
        assert workflow.topic == "Test Topic"
        assert workflow.description is None
        assert workflow.status == WorkflowStatus.PENDING
        assert workflow.report_url is None
        assert workflow.tasks == []

    def test_workflow_creation_with_description(self, sample_workflow_id):
        """验证 Workflow 带描述创建"""
        workflow = Workflow(
            workflow_id=sample_workflow_id,
            topic="Test Topic",
            description="Test description"
        )
        
        assert workflow.description == "Test description"

    def test_workflow_creation_auto_timestamp(self, sample_workflow_id):
        """验证 Workflow 自动时间戳"""
        workflow = Workflow(
            workflow_id=sample_workflow_id,
            topic="Test Topic"
        )
        
        assert workflow.created_at is not None
        assert workflow.updated_at is not None


class TestWorkflowTaskManagement:
    """Workflow 任务管理测试"""

    def test_workflow_add_task(self, sample_workflow, sample_task):
        """验证添加任务"""
        initial_updated_at = sample_workflow.updated_at
        sample_workflow.add_task(sample_task)
        
        assert len(sample_workflow.tasks) == 1
        assert sample_workflow.tasks[0] == sample_task
        assert sample_workflow.updated_at >= initial_updated_at

    def test_workflow_add_multiple_tasks(self, sample_workflow, sample_workflow_id):
        """验证添加多个任务"""
        for i in range(3):
            task = Task(
                task_id=f"task-{i}",
                workflow_id=sample_workflow_id,
                title=f"Task {i}",
                intent=f"Intent {i}",
                query=f"query {i}",
                order=i
            )
            sample_workflow.add_task(task)
        
        assert len(sample_workflow.tasks) == 3


class TestWorkflowStatusTransitions:
    """Workflow 状态转换测试"""

    def test_workflow_start_from_pending(self, sample_workflow):
        """验证从 PENDING 启动"""
        sample_workflow.start()
        
        assert sample_workflow.status == WorkflowStatus.RUNNING
        assert sample_workflow.started_at is not None

    def test_workflow_start_from_running_raises_error(self, sample_workflow):
        """验证从 RUNNING 启动抛出异常"""
        sample_workflow.start()
        
        with pytest.raises(InvalidWorkflowStateError):
            sample_workflow.start()

    def test_workflow_mark_all_success(self, sample_workflow):
        """验证标记全部成功"""
        sample_workflow.start()
        sample_workflow.mark_all_success("/reports/test")
        
        assert sample_workflow.status == WorkflowStatus.ALL_SUCCESS
        assert sample_workflow.report_url == "/reports/test"
        assert sample_workflow.completed_at is not None

    def test_workflow_mark_all_success_without_report_url(self, sample_workflow):
        """验证标记全部成功不带报告 URL"""
        sample_workflow.start()
        sample_workflow.mark_all_success()
        
        assert sample_workflow.status == WorkflowStatus.ALL_SUCCESS
        assert sample_workflow.report_url is None

    def test_workflow_mark_partial_failed(self, sample_workflow):
        """验证标记部分失败"""
        sample_workflow.start()
        sample_workflow.mark_partial_failed("/reports/test")
        
        assert sample_workflow.status == WorkflowStatus.PARTIAL_FAILED
        assert sample_workflow.report_url == "/reports/test"

    def test_workflow_mark_all_failed(self, sample_workflow):
        """验证标记全部失败"""
        sample_workflow.start()
        sample_workflow.mark_all_failed()
        
        assert sample_workflow.status == WorkflowStatus.ALL_FAILED
        assert sample_workflow.completed_at is not None

    def test_workflow_mark_report_failed(self, sample_workflow):
        """验证标记报告失败"""
        sample_workflow.start()
        sample_workflow.mark_report_failed()
        
        assert sample_workflow.status == WorkflowStatus.REPORT_FAILED

    def test_workflow_mark_success_from_pending_raises_error(self, sample_workflow):
        """验证从 PENDING 标记成功抛出异常"""
        with pytest.raises(InvalidWorkflowStateError):
            sample_workflow.mark_all_success()


class TestWorkflowStateQueries:
    """Workflow 状态查询测试"""

    def test_workflow_is_terminal_pending(self, sample_workflow):
        """验证 PENDING 不是终态"""
        assert not sample_workflow.is_terminal()

    def test_workflow_is_terminal_running(self, sample_workflow):
        """验证 RUNNING 不是终态"""
        sample_workflow.start()
        assert not sample_workflow.is_terminal()

    def test_workflow_is_terminal_all_success(self, sample_workflow):
        """验证 ALL_SUCCESS 是终态"""
        sample_workflow.start()
        sample_workflow.mark_all_success()
        assert sample_workflow.is_terminal()

    def test_workflow_is_success_all_success(self, sample_workflow):
        """验证 ALL_SUCCESS 是成功状态"""
        sample_workflow.start()
        sample_workflow.mark_all_success()
        assert sample_workflow.is_success()

    def test_workflow_is_success_partial_failed(self, sample_workflow):
        """验证 PARTIAL_FAILED 是成功状态"""
        sample_workflow.start()
        sample_workflow.mark_partial_failed()
        assert sample_workflow.is_success()

    def test_workflow_is_success_all_failed(self, sample_workflow):
        """验证 ALL_FAILED 不是成功状态"""
        sample_workflow.start()
        sample_workflow.mark_all_failed()
        assert not sample_workflow.is_success()

    def test_workflow_has_report_true(self, sample_workflow):
        """验证有报告"""
        sample_workflow.report_url = "/reports/test"
        assert sample_workflow.has_report()

    def test_workflow_has_report_false(self, sample_workflow):
        """验证无报告"""
        assert not sample_workflow.has_report()


class TestWorkflowTaskQueries:
    """Workflow 任务查询测试"""

    def test_workflow_get_pending_tasks(self, sample_workflow_with_tasks):
        """验证获取待处理任务"""
        pending_tasks = sample_workflow_with_tasks.get_pending_tasks()
        
        assert len(pending_tasks) == 1
        assert pending_tasks[0].status == TaskStatus.PENDING

    def test_workflow_get_running_tasks(self, sample_workflow_with_tasks):
        """验证获取运行中任务"""
        sample_workflow_with_tasks.tasks[0].start()
        running_tasks = sample_workflow_with_tasks.get_running_tasks()
        
        assert len(running_tasks) == 1
        assert running_tasks[0].status == TaskStatus.RUNNING

    def test_workflow_get_completed_tasks(self, sample_workflow_with_tasks):
        """验证获取已完成任务"""
        task = sample_workflow_with_tasks.tasks[0]
        task.start()
        task.complete("summary", "sources", "notices")
        
        completed_tasks = sample_workflow_with_tasks.get_completed_tasks()
        
        assert len(completed_tasks) == 1
        assert completed_tasks[0].status == TaskStatus.COMPLETED

    def test_workflow_get_tasks_empty(self, sample_workflow):
        """验证空任务列表"""
        assert sample_workflow.get_pending_tasks() == []
        assert sample_workflow.get_running_tasks() == []
        assert sample_workflow.get_completed_tasks() == []

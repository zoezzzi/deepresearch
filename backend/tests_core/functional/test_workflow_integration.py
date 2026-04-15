"""
工作流集成测试
测试工作流的完整流程
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from core.models import Workflow, Task, WorkflowStatus, TaskStatus


class TestWorkflowIntegration:
    """工作流集成测试"""

    @pytest.mark.asyncio
    async def test_workflow_with_multiple_tasks(self, sample_workflow_id):
        """验证工作流处理多个任务"""
        workflow = Workflow(
            workflow_id=sample_workflow_id,
            topic="Test Topic"
        )
        
        for i in range(3):
            task = Task(
                task_id=f"task-{i}",
                workflow_id=sample_workflow_id,
                title=f"Task {i}",
                intent=f"Intent {i}",
                query=f"query {i}",
                order=i
            )
            workflow.add_task(task)
        
        assert len(workflow.tasks) == 3
        assert workflow.get_pending_tasks() == workflow.tasks

    @pytest.mark.asyncio
    async def test_workflow_task_completion_flow(self, sample_workflow_id):
        """验证工作流任务完成流程"""
        workflow = Workflow(
            workflow_id=sample_workflow_id,
            topic="Test Topic"
        )
        
        task1 = Task(
            task_id="task-1",
            workflow_id=sample_workflow_id,
            title="Task 1",
            intent="Intent 1",
            query="query 1",
            order=1
        )
        task2 = Task(
            task_id="task-2",
            workflow_id=sample_workflow_id,
            title="Task 2",
            intent="Intent 2",
            query="query 2",
            order=2
        )
        
        workflow.add_task(task1)
        workflow.add_task(task2)
        
        workflow.start()
        assert workflow.status == WorkflowStatus.RUNNING
        
        task1.start()
        task1.complete("summary1", "sources1", "notices1")
        assert len(workflow.get_completed_tasks()) == 1
        
        task2.start()
        task2.complete("summary2", "sources2", "notices2")
        assert len(workflow.get_completed_tasks()) == 2
        
        workflow.mark_all_success("/reports/test")
        assert workflow.status == WorkflowStatus.ALL_SUCCESS

    @pytest.mark.asyncio
    async def test_workflow_partial_failure_flow(self, sample_workflow_id):
        """验证工作流部分失败流程"""
        workflow = Workflow(
            workflow_id=sample_workflow_id,
            topic="Test Topic"
        )
        
        task1 = Task(
            task_id="task-1",
            workflow_id=sample_workflow_id,
            title="Task 1",
            intent="Intent 1",
            query="query 1",
            order=1
        )
        task2 = Task(
            task_id="task-2",
            workflow_id=sample_workflow_id,
            title="Task 2",
            intent="Intent 2",
            query="query 2",
            order=2
        )
        
        workflow.add_task(task1)
        workflow.add_task(task2)
        
        workflow.start()
        
        task1.start()
        task1.complete("summary1", "sources1", "notices1")
        
        task2.start()
        task2.fail("Error occurred")
        
        workflow.mark_partial_failed("/reports/test")
        
        assert workflow.status == WorkflowStatus.PARTIAL_FAILED
        assert len(workflow.get_completed_tasks()) == 1
        assert len([t for t in workflow.tasks if t.status == TaskStatus.FAILED]) == 1


class TestWorkflowStateRecovery:
    """工作流状态恢复测试"""

    def test_workflow_state_from_tasks_completed(self, sample_workflow_id):
        """验证从任务状态推断工作流完成"""
        workflow = Workflow(
            workflow_id=sample_workflow_id,
            topic="Test Topic",
            status=WorkflowStatus.RUNNING
        )
        
        task = Task(
            task_id="task-1",
            workflow_id=sample_workflow_id,
            title="Task 1",
            intent="Intent 1",
            query="query 1",
            order=1
        )
        task.status = TaskStatus.COMPLETED
        workflow.add_task(task)
        
        completed = workflow.get_completed_tasks()
        assert len(completed) == 1
        assert completed[0].status == TaskStatus.COMPLETED

    def test_workflow_state_from_tasks_mixed(self, sample_workflow_id):
        """验证从任务状态推断工作流混合状态"""
        workflow = Workflow(
            workflow_id=sample_workflow_id,
            topic="Test Topic",
            status=WorkflowStatus.RUNNING
        )
        
        for i, status in enumerate([TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.PENDING]):
            task = Task(
                task_id=f"task-{i}",
                workflow_id=sample_workflow_id,
                title=f"Task {i}",
                intent=f"Intent {i}",
                query=f"query {i}",
                order=i
            )
            task.status = status
            workflow.add_task(task)
        
        assert len(workflow.get_completed_tasks()) == 1
        assert len([t for t in workflow.tasks if t.status == TaskStatus.FAILED]) == 1
        assert len(workflow.get_pending_tasks()) == 1

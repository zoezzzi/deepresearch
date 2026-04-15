"""
WorkflowState 测试
"""
import pytest
from datetime import datetime
from core.workflow.state import WorkflowState


class TestWorkflowState:
    """WorkflowState 测试"""

    def test_workflow_state_structure(self):
        """验证状态结构"""
        state: WorkflowState = {
            "workflow_id": "test-workflow-123",
            "topic": "Test Topic",
            "description": "Test description",
            "tasks": [],
            "current_task_index": 0,
            "task_results": [],
            "report_content": None,
            "report_url": None,
            "error": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        assert state["workflow_id"] == "test-workflow-123"
        assert state["topic"] == "Test Topic"
        assert state["tasks"] == []
        assert state["current_task_index"] == 0

    def test_workflow_state_with_tasks(self):
        """验证带任务的状态"""
        state: WorkflowState = {
            "workflow_id": "test-workflow-123",
            "topic": "Test Topic",
            "tasks": [
                {"task_id": "task-1", "title": "Task 1", "status": "pending"},
                {"task_id": "task-2", "title": "Task 2", "status": "completed"}
            ],
            "current_task_index": 1,
            "task_results": [],
            "report_content": None,
            "report_url": None,
            "error": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        assert len(state["tasks"]) == 2
        assert state["current_task_index"] == 1

    def test_workflow_state_with_report(self):
        """验证带报告的状态"""
        state: WorkflowState = {
            "workflow_id": "test-workflow-123",
            "topic": "Test Topic",
            "tasks": [],
            "current_task_index": 0,
            "task_results": [],
            "report_content": "# Report Content",
            "report_url": "/reports/test-report.md",
            "error": None,
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        assert state["report_content"] == "# Report Content"
        assert state["report_url"] == "/reports/test-report.md"

    def test_workflow_state_with_error(self):
        """验证带错误的状态"""
        state: WorkflowState = {
            "workflow_id": "test-workflow-123",
            "topic": "Test Topic",
            "tasks": [],
            "current_task_index": 0,
            "task_results": [],
            "report_content": None,
            "report_url": None,
            "error": "Something went wrong",
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        assert state["error"] == "Something went wrong"

    def test_workflow_state_optional_fields(self):
        """验证可选字段"""
        state: WorkflowState = {
            "workflow_id": "test-workflow-123",
            "topic": "Test Topic",
            "tasks": [],
            "current_task_index": 0,
            "task_results": [],
            "retrieved_chunks": ["chunk1", "chunk2"],
            "sub_questions": ["q1", "q2"],
            "citations": ["citation1"],
            "created_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        assert state["retrieved_chunks"] == ["chunk1", "chunk2"]
        assert state["sub_questions"] == ["q1", "q2"]
        assert state["citations"] == ["citation1"]

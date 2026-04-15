"""
枚举类型测试
测试 WorkflowStatus、TaskStatus、EvaluationStatus
"""
import pytest
from core.models.enums import WorkflowStatus, TaskStatus, EvaluationStatus


class TestWorkflowStatus:
    """WorkflowStatus 枚举测试"""

    def test_workflow_status_values(self):
        """验证 WorkflowStatus 所有枚举值"""
        assert WorkflowStatus.PENDING.value == "pending"
        assert WorkflowStatus.RUNNING.value == "running"
        assert WorkflowStatus.ALL_SUCCESS.value == "all_success"
        assert WorkflowStatus.PARTIAL_FAILED.value == "partial_failed"
        assert WorkflowStatus.ALL_FAILED.value == "all_failed"
        assert WorkflowStatus.REPORT_FAILED.value == "report_failed"

    def test_workflow_status_is_terminal_pending_not_terminal(self):
        """验证 PENDING 不是终态"""
        assert not WorkflowStatus.is_terminal_status(WorkflowStatus.PENDING)

    def test_workflow_status_is_terminal_running_not_terminal(self):
        """验证 RUNNING 不是终态"""
        assert not WorkflowStatus.is_terminal_status(WorkflowStatus.RUNNING)

    def test_workflow_status_is_terminal_all_success_is_terminal(self):
        """验证 ALL_SUCCESS 是终态"""
        assert WorkflowStatus.is_terminal_status(WorkflowStatus.ALL_SUCCESS)

    def test_workflow_status_is_terminal_partial_failed_is_terminal(self):
        """验证 PARTIAL_FAILED 是终态"""
        assert WorkflowStatus.is_terminal_status(WorkflowStatus.PARTIAL_FAILED)

    def test_workflow_status_is_terminal_all_failed_is_terminal(self):
        """验证 ALL_FAILED 是终态"""
        assert WorkflowStatus.is_terminal_status(WorkflowStatus.ALL_FAILED)

    def test_workflow_status_is_terminal_report_failed_is_terminal(self):
        """验证 REPORT_FAILED 是终态"""
        assert WorkflowStatus.is_terminal_status(WorkflowStatus.REPORT_FAILED)

    def test_workflow_status_from_string_valid(self):
        """验证有效字符串转换"""
        assert WorkflowStatus.from_string("pending") == WorkflowStatus.PENDING
        assert WorkflowStatus.from_string("running") == WorkflowStatus.RUNNING
        assert WorkflowStatus.from_string("all_success") == WorkflowStatus.ALL_SUCCESS

    def test_workflow_status_from_string_completed_alias(self):
        """验证 completed 别名转换为 ALL_SUCCESS"""
        assert WorkflowStatus.from_string("completed") == WorkflowStatus.ALL_SUCCESS

    def test_workflow_status_from_string_failed_alias(self):
        """验证 failed 别名转换为 ALL_FAILED"""
        assert WorkflowStatus.from_string("failed") == WorkflowStatus.ALL_FAILED

    def test_workflow_status_from_string_invalid(self):
        """验证无效字符串抛出异常"""
        with pytest.raises(ValueError, match="Invalid workflow status"):
            WorkflowStatus.from_string("invalid_status")

    def test_workflow_status_to_display_status_completed(self):
        """验证终态显示为 completed"""
        assert WorkflowStatus.to_display_status(WorkflowStatus.ALL_SUCCESS) == "completed"
        assert WorkflowStatus.to_display_status(WorkflowStatus.PARTIAL_FAILED) == "completed"

    def test_workflow_status_to_display_status_failed(self):
        """验证失败状态显示为 failed"""
        assert WorkflowStatus.to_display_status(WorkflowStatus.ALL_FAILED) == "failed"
        assert WorkflowStatus.to_display_status(WorkflowStatus.REPORT_FAILED) == "failed"

    def test_workflow_status_to_display_status_in_progress(self):
        """验证进行中状态显示原值"""
        assert WorkflowStatus.to_display_status(WorkflowStatus.PENDING) == "pending"
        assert WorkflowStatus.to_display_status(WorkflowStatus.RUNNING) == "running"


class TestTaskStatus:
    """TaskStatus 枚举测试"""

    def test_task_status_values(self):
        """验证 TaskStatus 所有枚举值"""
        assert TaskStatus.PENDING.value == "pending"
        assert TaskStatus.RUNNING.value == "running"
        assert TaskStatus.COMPLETED.value == "completed"
        assert TaskStatus.FAILED.value == "failed"

    def test_task_status_string_equality(self):
        """验证 TaskStatus 字符串相等性"""
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"


class TestEvaluationStatus:
    """EvaluationStatus 枚举测试"""

    def test_evaluation_status_values(self):
        """验证 EvaluationStatus 所有枚举值"""
        assert EvaluationStatus.PENDING.value == "pending"
        assert EvaluationStatus.IN_PROGRESS.value == "in_progress"
        assert EvaluationStatus.COMPLETED.value == "completed"
        assert EvaluationStatus.FAILED.value == "failed"

    def test_evaluation_status_string_equality(self):
        """验证 EvaluationStatus 字符串相等性"""
        assert EvaluationStatus.PENDING == "pending"
        assert EvaluationStatus.IN_PROGRESS == "in_progress"
        assert EvaluationStatus.COMPLETED == "completed"
        assert EvaluationStatus.FAILED == "failed"

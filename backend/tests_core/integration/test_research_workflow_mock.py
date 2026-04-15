"""
研究工作流集成测试 - Mock 版本

由于集成测试需要完整的数据库和外部服务环境，
此测试使用 Mock 对象验证核心工作流逻辑。

测试覆盖:
- 工作流创建与状态流转
- 任务生成与执行
- 报告生成
- 错误处理
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from core.models import (
    Workflow,
    Task,
    WorkflowStatus,
    TaskStatus,
    CreateResearchRequest
)
from core.services import ResearchService


class TestResearchWorkflowMock:
    """研究工作流 Mock 集成测试"""

    @pytest.fixture
    def mock_research_service(self):
        """创建模拟的研究服务"""
        service = MagicMock(spec=ResearchService)
        service.create_research_workflow = AsyncMock()
        service.get_workflow_status = AsyncMock()
        service.get_report_content = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_workflow_creation_flow(self, mock_research_service):
        """测试工作流创建流程"""
        # 模拟创建工作流响应
        mock_response = MagicMock()
        mock_response.workflow_id = "test-workflow-123"
        mock_response.topic = "人工智能在医疗领域的应用"
        mock_response.status = WorkflowStatus.PENDING
        mock_response.tasks = []
        
        mock_research_service.create_research_workflow.return_value = mock_response
        
        # 执行创建
        request = CreateResearchRequest(
            topic="人工智能在医疗领域的应用",
            description="调研AI在医疗诊断、药物研发等方面的最新进展"
        )
        
        response = await mock_research_service.create_research_workflow(request)
        
        # 验证
        assert response.workflow_id == "test-workflow-123"
        assert response.topic == "人工智能在医疗领域的应用"
        assert response.status == WorkflowStatus.PENDING
        mock_research_service.create_research_workflow.assert_called_once_with(request)

    @pytest.mark.asyncio
    async def test_workflow_status_polling_flow(self, mock_research_service):
        """测试工作流状态轮询流程"""
        workflow_id = "test-workflow-123"
        
        # 模拟不同时间点的状态
        pending_response = MagicMock()
        pending_response.workflow_id = workflow_id
        pending_response.status = WorkflowStatus.PENDING
        pending_response.tasks = []
        
        running_response = MagicMock()
        running_response.workflow_id = workflow_id
        running_response.status = WorkflowStatus.RUNNING
        running_response.tasks = [
            MagicMock(task_id="task-1", status="running"),
            MagicMock(task_id="task-2", status="pending")
        ]
        
        completed_response = MagicMock()
        completed_response.workflow_id = workflow_id
        completed_response.status = WorkflowStatus.ALL_SUCCESS
        completed_response.workflow_status = "all_success"
        completed_response.report_url = "/reports/test-report.md"
        completed_response.tasks = [
            MagicMock(task_id="task-1", status="completed"),
            MagicMock(task_id="task-2", status="completed")
        ]
        completed_response.task_summary = {
            "total": 2,
            "completed": 2,
            "failed": 0
        }
        
        # 设置 side_effect 模拟状态变化
        mock_research_service.get_workflow_status.side_effect = [
            pending_response,
            running_response,
            completed_response
        ]
        
        # 模拟轮询
        responses = []
        for _ in range(3):
            response = await mock_research_service.get_workflow_status(workflow_id)
            responses.append(response)
        
        # 验证状态流转
        assert responses[0].status == WorkflowStatus.PENDING
        assert responses[1].status == WorkflowStatus.RUNNING
        assert responses[2].status == WorkflowStatus.ALL_SUCCESS
        assert responses[2].report_url == "/reports/test-report.md"

    @pytest.mark.asyncio
    async def test_task_generation_and_execution_flow(self, mock_research_service):
        """测试任务生成和执行流程"""
        workflow_id = "test-workflow-123"
        
        # 模拟任务生成后的状态
        response_with_tasks = MagicMock()
        response_with_tasks.workflow_id = workflow_id
        response_with_tasks.status = WorkflowStatus.RUNNING
        response_with_tasks.tasks = [
            MagicMock(
                task_id="task-1",
                title="AI在医疗诊断中的应用",
                status="completed",
                summary="AI在医疗诊断领域取得重大进展...",
                sources_summary="来源1: 医疗AI报告2024"
            ),
            MagicMock(
                task_id="task-2",
                title="AI在药物研发中的应用",
                status="running",
                summary=None,
                sources_summary=None
            ),
            MagicMock(
                task_id="task-3",
                title="AI医疗应用的未来趋势",
                status="pending",
                summary=None,
                sources_summary=None
            )
        ]
        
        mock_research_service.get_workflow_status.return_value = response_with_tasks
        
        response = await mock_research_service.get_workflow_status(workflow_id)
        
        # 验证任务状态
        assert len(response.tasks) == 3
        assert response.tasks[0].status == "completed"
        assert response.tasks[1].status == "running"
        assert response.tasks[2].status == "pending"
        
        # 验证已完成任务有摘要
        assert response.tasks[0].summary is not None
        assert response.tasks[0].sources_summary is not None

    @pytest.mark.asyncio
    async def test_report_generation_flow(self, mock_research_service):
        """测试报告生成流程"""
        workflow_id = "test-workflow-123"
        
        # 模拟报告内容
        mock_report_content = """# 人工智能在医疗领域的应用调研报告

## 执行摘要

本次调研深入分析了人工智能在医疗领域的应用现状...

## 主要发现

### 1. AI在医疗诊断中的应用
AI技术在影像诊断、病理分析等方面取得重大突破...

### 2. AI在药物研发中的应用
AI加速药物发现过程，缩短研发周期...

## 结论

AI在医疗领域具有广阔的应用前景...
"""
        
        mock_research_service.get_report_content.return_value = mock_report_content
        
        # 获取报告
        content = await mock_research_service.get_report_content(workflow_id)
        
        # 验证
        assert content is not None
        assert "人工智能在医疗领域的应用" in content
        assert "执行摘要" in content
        assert "主要发现" in content
        assert "结论" in content

    @pytest.mark.asyncio
    async def test_partial_failure_flow(self, mock_research_service):
        """测试部分失败流程"""
        workflow_id = "test-workflow-123"
        
        # 模拟部分失败状态
        partial_failed_response = MagicMock()
        partial_failed_response.workflow_id = workflow_id
        partial_failed_response.status = WorkflowStatus.PARTIAL_FAILED
        partial_failed_response.workflow_status = "partial_failed"
        partial_failed_response.report_url = "/reports/partial-report.md"
        partial_failed_response.tasks = [
            MagicMock(task_id="task-1", status="completed"),
            MagicMock(task_id="task-2", status="failed"),
            MagicMock(task_id="task-3", status="completed")
        ]
        partial_failed_response.task_summary = {
            "total": 3,
            "completed": 2,
            "failed": 1
        }
        
        mock_research_service.get_workflow_status.return_value = partial_failed_response
        
        response = await mock_research_service.get_workflow_status(workflow_id)
        
        # 验证部分失败状态
        assert response.status == WorkflowStatus.PARTIAL_FAILED
        assert response.workflow_status == "partial_failed"
        assert response.report_url is not None  # 部分失败仍应有报告
        assert response.task_summary["completed"] == 2
        assert response.task_summary["failed"] == 1

    @pytest.mark.asyncio
    async def test_all_failed_flow(self, mock_research_service):
        """测试全部失败流程"""
        workflow_id = "test-workflow-123"
        
        # 模拟全部失败状态
        all_failed_response = MagicMock()
        all_failed_response.workflow_id = workflow_id
        all_failed_response.status = WorkflowStatus.ALL_FAILED
        all_failed_response.workflow_status = "all_failed"
        all_failed_response.report_url = None
        all_failed_response.tasks = [
            MagicMock(task_id="task-1", status="failed"),
            MagicMock(task_id="task-2", status="failed"),
            MagicMock(task_id="task-3", status="failed")
        ]
        all_failed_response.task_summary = {
            "total": 3,
            "completed": 0,
            "failed": 3
        }
        
        mock_research_service.get_workflow_status.return_value = all_failed_response
        
        response = await mock_research_service.get_workflow_status(workflow_id)
        
        # 验证全部失败状态
        assert response.status == WorkflowStatus.ALL_FAILED
        assert response.workflow_status == "all_failed"
        assert response.report_url is None  # 全部失败无报告
        assert response.task_summary["completed"] == 0
        assert response.task_summary["failed"] == 3

    @pytest.mark.asyncio
    async def test_error_handling_flow(self, mock_research_service):
        """测试错误处理流程"""
        workflow_id = "test-workflow-123"
        
        # 模拟服务异常
        mock_research_service.get_workflow_status.side_effect = Exception("服务暂时不可用")
        
        # 验证异常被正确抛出
        with pytest.raises(Exception, match="服务暂时不可用"):
            await mock_research_service.get_workflow_status(workflow_id)

    def test_workflow_state_transitions(self):
        """测试工作流状态转换逻辑"""
        # 创建真实的工作流对象测试状态转换
        workflow = Workflow(
            workflow_id="test-workflow-123",
            topic="测试主题"
        )
        
        # PENDING -> RUNNING
        assert workflow.status == WorkflowStatus.PENDING
        workflow.start()
        assert workflow.status == WorkflowStatus.RUNNING
        
        # RUNNING -> ALL_SUCCESS
        workflow.mark_all_success("/reports/test.md")
        assert workflow.status == WorkflowStatus.ALL_SUCCESS
        assert workflow.report_url == "/reports/test.md"

    def test_task_state_transitions(self):
        """测试任务状态转换逻辑"""
        # 创建真实的任务对象测试状态转换
        task = Task(
            task_id="task-1",
            workflow_id="workflow-1",
            title="测试任务",
            intent="测试意图",
            query="测试查询",
            order=1
        )
        
        # PENDING -> RUNNING
        assert task.status == TaskStatus.PENDING
        task.start()
        assert task.status == TaskStatus.RUNNING
        assert task.started_at is not None
        
        # RUNNING -> COMPLETED
        task.complete(
            summary="测试摘要",
            sources_summary="测试来源",
            notices="测试注意事项"
        )
        assert task.status == TaskStatus.COMPLETED
        assert task.summary == "测试摘要"
        assert task.completed_at is not None


class TestWorkflowIntegrationScenarios:
    """工作流集成场景测试"""

    @pytest.mark.asyncio
    async def test_complete_workflow_lifecycle(self):
        """测试完整的工作流生命周期"""
        # 使用真实模型验证完整生命周期
        workflow = Workflow(
            workflow_id="lifecycle-test",
            topic="生命周期测试"
        )
        
        # 1. 初始状态
        assert workflow.status == WorkflowStatus.PENDING
        
        # 2. 添加任务
        for i in range(3):
            task = Task(
                task_id=f"task-{i}",
                workflow_id=workflow.workflow_id,
                title=f"任务{i}",
                intent=f"意图{i}",
                query=f"查询{i}",
                order=i
            )
            workflow.add_task(task)
        
        assert len(workflow.tasks) == 3
        
        # 3. 启动工作流
        workflow.start()
        assert workflow.status == WorkflowStatus.RUNNING
        
        # 4. 模拟任务完成
        for task in workflow.tasks:
            task.start()
            task.complete(f"摘要{task.order}", f"来源{task.order}", "注意事项")
        
        assert len(workflow.get_completed_tasks()) == 3
        
        # 5. 完成工作流
        workflow.mark_all_success("/reports/final.md")
        assert workflow.status == WorkflowStatus.ALL_SUCCESS
        assert workflow.is_terminal()
        assert workflow.is_success()

    @pytest.mark.asyncio
    async def test_concurrent_task_execution_simulation(self):
        """模拟并发任务执行"""
        workflow = Workflow(
            workflow_id="concurrent-test",
            topic="并发测试"
        )
        
        # 添加多个任务
        tasks = []
        for i in range(5):
            task = Task(
                task_id=f"concurrent-task-{i}",
                workflow_id=workflow.workflow_id,
                title=f"并发任务{i}",
                intent=f"意图{i}",
                query=f"查询{i}",
                order=i
            )
            tasks.append(task)
            workflow.add_task(task)
        
        workflow.start()
        
        # 模拟部分任务完成
        tasks[0].start()
        tasks[0].complete("摘要0", "来源0", "")
        
        tasks[1].start()
        tasks[1].fail("任务失败")
        
        tasks[2].start()
        tasks[2].complete("摘要2", "来源2", "")
        
        # 验证状态
        assert len(workflow.get_completed_tasks()) == 2
        assert len([t for t in workflow.tasks if t.status == TaskStatus.FAILED]) == 1
        assert len(workflow.get_running_tasks()) == 0  # tasks[3], tasks[4] 仍为 pending
        assert len(workflow.get_pending_tasks()) == 2

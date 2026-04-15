"""
DTO 测试
测试数据传输对象
"""
import pytest
from pydantic import ValidationError
from core.models import (
    CreateResearchRequest,
    WorkflowResponse,
    TaskResponse,
    ResearchResponse,
    WorkflowStatus
)
from datetime import datetime


class TestCreateResearchRequest:
    """CreateResearchRequest 测试"""

    def test_create_research_request_valid(self):
        """验证有效的创建请求"""
        request = CreateResearchRequest(topic="Test Topic")
        
        assert request.topic == "Test Topic"
        assert request.description is None

    def test_create_research_request_with_description(self):
        """验证带描述的创建请求"""
        request = CreateResearchRequest(
            topic="Test Topic",
            description="Test Description"
        )
        
        assert request.topic == "Test Topic"
        assert request.description == "Test Description"

    def test_create_research_request_empty_topic(self):
        """验证空主题抛出验证错误"""
        with pytest.raises(ValidationError):
            CreateResearchRequest(topic="")

    def test_create_research_request_whitespace_topic(self):
        """验证空白主题抛出验证错误"""
        with pytest.raises(ValidationError):
            CreateResearchRequest(topic="   ")


class TestTaskResponse:
    """TaskResponse 测试"""

    def test_task_response_creation(self):
        """验证任务响应创建"""
        now = datetime.now()
        response = TaskResponse(
            task_id="task-1",
            title="Test Task",
            intent="Test Intent",
            query="test query",
            order=1,
            status="pending",
            summary="Test summary",
            sources_summary="Test sources",
            notices="Test notices",
            created_at=now,
            updated_at=now
        )
        
        assert response.task_id == "task-1"
        assert response.title == "Test Task"
        assert response.status == "pending"

    def test_task_response_optional_fields(self):
        """验证任务响应可选字段"""
        now = datetime.now()
        response = TaskResponse(
            task_id="task-1",
            title="Test Task",
            intent="Test Intent",
            query="test query",
            order=1,
            status="pending",
            created_at=now,
            updated_at=now
        )
        
        assert response.summary is None
        assert response.sources_summary is None
        assert response.notices is None


class TestWorkflowResponse:
    """WorkflowResponse 测试"""

    def test_workflow_response_creation(self):
        """验证工作流响应创建"""
        now = datetime.now()
        response = WorkflowResponse(
            workflow_id="workflow-1",
            topic="Test Topic",
            description="Test Description",
            status=WorkflowStatus.PENDING,
            report_url=None,
            created_at=now,
            updated_at=now,
            tasks=[]
        )
        
        assert response.workflow_id == "workflow-1"
        assert response.topic == "Test Topic"
        assert response.status == WorkflowStatus.PENDING

    def test_workflow_response_with_tasks(self):
        """验证带任务的工作流响应"""
        now = datetime.now()
        task_response = TaskResponse(
            task_id="task-1",
            title="Test Task",
            intent="Test Intent",
            query="test query",
            order=1,
            status="pending",
            created_at=now,
            updated_at=now
        )
        
        response = WorkflowResponse(
            workflow_id="workflow-1",
            topic="Test Topic",
            status=WorkflowStatus.RUNNING,
            created_at=now,
            updated_at=now,
            tasks=[task_response]
        )
        
        assert len(response.tasks) == 1
        assert response.tasks[0].task_id == "task-1"


class TestResearchResponse:
    """ResearchResponse 测试"""

    def test_research_response_creation(self):
        """验证研究响应创建"""
        now = datetime.now()
        response = ResearchResponse(
            workflow_id="workflow-1",
            topic="Test Topic",
            status=WorkflowStatus.ALL_SUCCESS,
            report_url="/reports/test.md",
            created_at=now,
            updated_at=now,
            tasks=[]
        )
        
        assert response.workflow_id == "workflow-1"
        assert response.status == WorkflowStatus.ALL_SUCCESS
        assert response.report_url == "/reports/test.md"

    def test_research_response_inherits_workflow_response(self):
        """验证研究响应继承工作流响应"""
        now = datetime.now()
        response = ResearchResponse(
            workflow_id="workflow-1",
            topic="Test Topic",
            status=WorkflowStatus.PENDING,
            created_at=now,
            updated_at=now,
            tasks=[]
        )
        
        assert hasattr(response, 'workflow_id')
        assert hasattr(response, 'topic')
        assert hasattr(response, 'status')
        assert hasattr(response, 'tasks')

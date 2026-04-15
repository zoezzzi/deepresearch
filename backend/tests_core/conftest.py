"""
Core 模块测试配置
提供共享的 fixtures 和测试工具
"""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Dict, Any

from core.models import (
    Task,
    Workflow,
    ResearchReport,
    EvaluationResult,
    WorkflowStatus,
    TaskStatus,
    EvaluationStatus
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_task_id() -> str:
    return "test-task-123"


@pytest.fixture
def sample_workflow_id() -> str:
    return "test-workflow-456"


@pytest.fixture
def sample_evaluation_id() -> str:
    return "test-evaluation-789"


@pytest.fixture
def sample_task(sample_task_id: str, sample_workflow_id: str) -> Task:
    return Task(
        task_id=sample_task_id,
        workflow_id=sample_workflow_id,
        title="Test Task",
        intent="Test intent",
        query="test query",
        order=1
    )


@pytest.fixture
def sample_workflow(sample_workflow_id: str) -> Workflow:
    return Workflow(
        workflow_id=sample_workflow_id,
        topic="Test Topic",
        description="Test description"
    )


@pytest.fixture
def sample_workflow_with_tasks(sample_workflow_id: str, sample_task_id: str) -> Workflow:
    workflow = Workflow(
        workflow_id=sample_workflow_id,
        topic="Test Topic",
        description="Test description"
    )
    task = Task(
        task_id=sample_task_id,
        workflow_id=sample_workflow_id,
        title="Test Task",
        intent="Test intent",
        query="test query",
        order=1
    )
    workflow.add_task(task)
    return workflow


@pytest.fixture
def sample_research_report(sample_workflow_id: str) -> ResearchReport:
    return ResearchReport(
        report_id="test-report-123",
        workflow_id=sample_workflow_id,
        content="# Test Report\n\nThis is a test report.",
        url="/reports/test-report-123"
    )


@pytest.fixture
def sample_evaluation_result(sample_evaluation_id: str, sample_workflow_id: str) -> EvaluationResult:
    return EvaluationResult(
        evaluation_id=sample_evaluation_id,
        workflow_id=sample_workflow_id
    )


@pytest.fixture
def mock_llm_client():
    client = AsyncMock()
    client.chat = AsyncMock(return_value="Mock LLM response")
    return client


@pytest.fixture
def mock_search_source():
    source = AsyncMock()
    
    mock_result = MagicMock()
    mock_result.title = "Test Result"
    mock_result.url = "https://example.com"
    mock_result.content = "Test content for search result"
    
    source.search = AsyncMock(return_value=[mock_result])
    return source


@pytest.fixture
def mock_workflow_repository():
    repo = AsyncMock()
    repo.save = AsyncMock()
    repo.find_by_id = AsyncMock()
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def mock_task_repository():
    repo = AsyncMock()
    repo.save = AsyncMock()
    repo.save_batch = AsyncMock()
    repo.find_by_id = AsyncMock()
    repo.find_by_workflow_id = AsyncMock(return_value=[])
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def mock_evaluation_repository():
    repo = AsyncMock()
    repo.save = AsyncMock()
    repo.find_by_id = AsyncMock()
    repo.find_by_workflow_id = AsyncMock(return_value=[])
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def mock_event_publisher():
    publisher = AsyncMock()
    publisher.publish_plan_event = AsyncMock()
    publisher.publish_task_start_event = AsyncMock()
    publisher.publish_task_complete_event = AsyncMock()
    publisher.publish_result_event = AsyncMock()
    publisher.publish_error_event = AsyncMock()
    return publisher


@pytest.fixture
def mock_object_storage():
    storage = AsyncMock()
    storage.upload_object = AsyncMock(return_value="/reports/test-report.md")
    storage.read_file = AsyncMock(return_value="# Test Report")
    storage.get_report_url_by_workflow_id = AsyncMock(return_value=None)
    return storage


@pytest.fixture
def mock_evaluation_orchestrator():
    orchestrator = AsyncMock()
    orchestrator.evaluate_all = AsyncMock(return_value={
        "scores": {
            "faithfulness": 0.85,
            "context_relevancy": 0.90,
            "coverage": 0.80,
            "structure": 0.88,
            "professional_depth": 0.92,
            "overall_score": 0.87
        },
        "details": {}
    })
    return orchestrator

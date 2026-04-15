"""
EvaluationService 测试
"""
import pytest
from unittest.mock import AsyncMock
from core.services.evaluation_service import EvaluationService
from core.models import EvaluationResult, EvaluationStatus


class TestEvaluationService:
    """EvaluationService 测试"""

    @pytest.fixture
    def evaluation_service(self, mock_evaluation_repository):
        """创建 EvaluationService fixture"""
        return EvaluationService(mock_evaluation_repository)

    @pytest.mark.asyncio
    async def test_create_evaluation(self, evaluation_service, mock_evaluation_repository, sample_workflow_id):
        """验证创建评估"""
        evaluation = await evaluation_service.create_evaluation(sample_workflow_id)
        
        assert evaluation is not None
        assert evaluation.workflow_id == sample_workflow_id
        assert evaluation.status == EvaluationStatus.PENDING
        mock_evaluation_repository.save.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_evaluation(self, evaluation_service, mock_evaluation_repository, sample_evaluation_id, sample_workflow_id):
        """验证开始评估"""
        existing_evaluation = EvaluationResult(
            evaluation_id=sample_evaluation_id,
            workflow_id=sample_workflow_id
        )
        mock_evaluation_repository.find_by_id.return_value = existing_evaluation
        
        evaluation = await evaluation_service.start_evaluation(sample_evaluation_id)
        
        assert evaluation.status == EvaluationStatus.IN_PROGRESS
        mock_evaluation_repository.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_evaluation_not_found(self, evaluation_service, mock_evaluation_repository, sample_evaluation_id):
        """验证开始评估时评估不存在"""
        mock_evaluation_repository.find_by_id.return_value = None
        
        with pytest.raises(ValueError, match="Evaluation not found"):
            await evaluation_service.start_evaluation(sample_evaluation_id)

    @pytest.mark.asyncio
    async def test_complete_evaluation(self, evaluation_service, mock_evaluation_repository, sample_evaluation_id, sample_workflow_id):
        """验证完成评估"""
        existing_evaluation = EvaluationResult(
            evaluation_id=sample_evaluation_id,
            workflow_id=sample_workflow_id
        )
        existing_evaluation.start()
        mock_evaluation_repository.find_by_id.return_value = existing_evaluation
        
        scores = {
            "faithfulness": 0.85,
            "context_relevancy": 0.90,
            "coverage": 0.80,
            "structure": 0.88,
            "professional_depth": 0.92,
            "overall_score": 0.87
        }
        
        evaluation = await evaluation_service.complete_evaluation(sample_evaluation_id, scores)
        
        assert evaluation.status == EvaluationStatus.COMPLETED
        assert evaluation.faithfulness == 0.85
        assert evaluation.overall_score == 0.87
        mock_evaluation_repository.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_fail_evaluation(self, evaluation_service, mock_evaluation_repository, sample_evaluation_id, sample_workflow_id):
        """验证评估失败"""
        existing_evaluation = EvaluationResult(
            evaluation_id=sample_evaluation_id,
            workflow_id=sample_workflow_id
        )
        existing_evaluation.start()
        mock_evaluation_repository.find_by_id.return_value = existing_evaluation
        
        evaluation = await evaluation_service.fail_evaluation(sample_evaluation_id, "Test error")
        
        assert evaluation.status == EvaluationStatus.FAILED
        assert evaluation.error_message == "Test error"
        mock_evaluation_repository.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_evaluation_by_workflow(self, evaluation_service, mock_evaluation_repository, sample_workflow_id, sample_evaluation_id):
        """验证根据工作流 ID 获取评估"""
        evaluation = EvaluationResult(
            evaluation_id=sample_evaluation_id,
            workflow_id=sample_workflow_id
        )
        mock_evaluation_repository.find_by_workflow_id.return_value = [evaluation]
        
        results = await evaluation_service.get_evaluation_by_workflow(sample_workflow_id)
        
        assert len(results) == 1
        mock_evaluation_repository.find_by_workflow_id.assert_called_once_with(sample_workflow_id)

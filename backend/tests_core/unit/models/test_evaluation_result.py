"""
EvaluationResult 模型测试
"""
import pytest
from core.models import EvaluationResult, EvaluationStatus


class TestEvaluationResultCreation:
    """EvaluationResult 创建测试"""

    def test_evaluation_creation_basic(self, sample_evaluation_id, sample_workflow_id):
        """验证 EvaluationResult 基本创建"""
        evaluation = EvaluationResult(
            evaluation_id=sample_evaluation_id,
            workflow_id=sample_workflow_id
        )
        
        assert evaluation.evaluation_id == sample_evaluation_id
        assert evaluation.workflow_id == sample_workflow_id
        assert evaluation.status == EvaluationStatus.PENDING

    def test_evaluation_creation_default_scores(self, sample_evaluation_result):
        """验证 EvaluationResult 默认分数"""
        assert sample_evaluation_result.faithfulness is None
        assert sample_evaluation_result.context_relevancy is None
        assert sample_evaluation_result.coverage is None
        assert sample_evaluation_result.structure is None
        assert sample_evaluation_result.professional_depth is None
        assert sample_evaluation_result.overall_score is None

    def test_evaluation_creation_auto_timestamp(self, sample_evaluation_result):
        """验证 EvaluationResult 自动时间戳"""
        assert sample_evaluation_result.created_at is not None
        assert sample_evaluation_result.updated_at is not None


class TestEvaluationResultStatusTransitions:
    """EvaluationResult 状态转换测试"""

    def test_evaluation_start(self, sample_evaluation_result):
        """验证评估开始"""
        sample_evaluation_result.start()
        
        assert sample_evaluation_result.status == EvaluationStatus.IN_PROGRESS
        assert sample_evaluation_result.started_at is not None

    def test_evaluation_complete(self, sample_evaluation_result):
        """验证评估完成"""
        sample_evaluation_result.start()
        sample_evaluation_result.complete(
            faithfulness=0.85,
            context_relevancy=0.90,
            coverage=0.80,
            structure=0.88,
            professional_depth=0.92,
            overall_score=0.87
        )
        
        assert sample_evaluation_result.status == EvaluationStatus.COMPLETED
        assert sample_evaluation_result.faithfulness == 0.85
        assert sample_evaluation_result.context_relevancy == 0.90
        assert sample_evaluation_result.coverage == 0.80
        assert sample_evaluation_result.structure == 0.88
        assert sample_evaluation_result.professional_depth == 0.92
        assert sample_evaluation_result.overall_score == 0.87
        assert sample_evaluation_result.completed_at is not None

    def test_evaluation_complete_with_details(self, sample_evaluation_result):
        """验证评估完成带详情"""
        details = {"question_scores": {"q1": 0.9, "q2": 0.8}}
        sample_evaluation_result.start()
        sample_evaluation_result.complete(
            faithfulness=0.85,
            context_relevancy=0.90,
            coverage=0.80,
            structure=0.88,
            professional_depth=0.92,
            overall_score=0.87,
            evaluation_details=details
        )
        
        assert sample_evaluation_result.evaluation_details == details

    def test_evaluation_fail(self, sample_evaluation_result):
        """验证评估失败"""
        sample_evaluation_result.start()
        sample_evaluation_result.fail("Test error message")
        
        assert sample_evaluation_result.status == EvaluationStatus.FAILED
        assert sample_evaluation_result.error_message == "Test error message"
        assert sample_evaluation_result.completed_at is not None


class TestEvaluationResultSerialization:
    """EvaluationResult 序列化测试"""

    def test_evaluation_model_dump(self, sample_evaluation_result):
        """验证 EvaluationResult 模型转字典"""
        data = sample_evaluation_result.model_dump()
        
        assert data["evaluation_id"] == sample_evaluation_result.evaluation_id
        assert data["workflow_id"] == sample_evaluation_result.workflow_id
        assert data["status"] == EvaluationStatus.PENDING

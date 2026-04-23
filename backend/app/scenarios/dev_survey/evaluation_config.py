from typing import List, Dict
from harness.evaluation.base_evaluator import BaseEvaluator
from app.dev_survey.evaluators import (
    AccuracyEvaluator,
    ComplianceEvaluator,
    ActionabilityEvaluator
)


def get_evaluators(llm_client=None) -> List[BaseEvaluator]:
    """获取 dev_survey 场景的评估器列表 - v2.0"""
    return [
        AccuracyEvaluator(llm_client),
        ComplianceEvaluator(llm_client),
        ActionabilityEvaluator(llm_client)
    ]


def get_weights() -> Dict[str, float]:
    """获取 dev_survey 场景的评估权重配置 - v2.0"""
    return {
        "technical_faithfulness": 0.25,
        "source_quality": 0.12,
        "checklist_coverage": 0.13,
        "template_compliance": 0.10,
        "actionability": 0.20,
        "decision_clarity": 0.15,
        "citation_coverage": 0.05
    }

from typing import List, Dict
from harness.evaluation.base_evaluator import BaseEvaluator
from harness.evaluation.ragas_evaluator import RAGASEvaluator
from harness.evaluation.llm_judge_evaluator import LLMJudgeEvaluator
from harness.evaluation.rule_evaluator import RuleBasedEvaluator


def get_evaluators(llm_client=None) -> List[BaseEvaluator]:
    """获取 research_assistant 场景的评估器列表"""
    return [
        RAGASEvaluator(llm_client),
        LLMJudgeEvaluator(llm_client),
        RuleBasedEvaluator()
    ]


def get_weights() -> Dict[str, float]:
    """获取 research_assistant 场景的评估权重配置"""
    return {
        "faithfulness": 0.3,
        "context_relevancy": 0.2,
        "coverage": 0.2,
        "structure": 0.15,
        "professional_depth": 0.15
    }

from typing import Dict, Any, List
import asyncio
from .base_evaluator import BaseEvaluator
from .ragas_evaluator import RAGASEvaluator
from .llm_judge_evaluator import LLMJudgeEvaluator
from .rule_evaluator import RuleBasedEvaluator
from harness.logger import logger


class EvaluationOrchestrator:
    def __init__(self, llm_client):
        self.evaluators: List[BaseEvaluator] = [
            RAGASEvaluator(llm_client),
            LLMJudgeEvaluator(llm_client),
            RuleBasedEvaluator()
        ]
        self.weights = {
            "faithfulness": 0.3,
            "context_relevancy": 0.2,
            "coverage": 0.2,
            "structure": 0.15,
            "professional_depth": 0.15
        }

    async def evaluate_all(
        self,
        report: str,
        contexts: List[str],
        question: str,
        sub_questions: List[str],
        citations: List[str]
    ) -> Dict[str, Any]:
        logger.info("[EvaluationOrchestrator] Starting evaluation orchestration")
        
        all_scores = {}
        all_details = {}
        
        tasks = []
        for evaluator in self.evaluators:
            if isinstance(evaluator, RAGASEvaluator):
                tasks.append(evaluator.evaluate(
                    answer=report,
                    contexts=contexts,
                    question=question
                ))
            elif isinstance(evaluator, LLMJudgeEvaluator):
                tasks.append(evaluator.evaluate(
                    report=report,
                    sub_questions=sub_questions
                ))
            elif isinstance(evaluator, RuleBasedEvaluator):
                tasks.append(evaluator.evaluate(
                    report=report,
                    citations=citations
                ))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"[EvaluationOrchestrator] Evaluator {i} failed: {str(result)}")
                continue
            all_scores.update(result)
        
        overall_score = self._calculate_overall_score(all_scores)
        all_scores["overall_score"] = overall_score
        
        logger.info(f"[EvaluationOrchestrator] All scores: {all_scores}")
        return {
            "scores": all_scores,
            "details": all_details
        }

    def _calculate_overall_score(self, scores: Dict[str, float]) -> float:
        total = 0.0
        weight_sum = 0.0
        
        for metric, weight in self.weights.items():
            if metric in scores and scores[metric] is not None:
                total += scores[metric] * weight
                weight_sum += weight
        
        if weight_sum == 0:
            return 0.5
        
        return total / weight_sum

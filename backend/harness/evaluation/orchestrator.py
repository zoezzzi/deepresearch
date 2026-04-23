from typing import Dict, Any, List
import asyncio
from .base_evaluator import BaseEvaluator
from harness.logger import logger


class EvaluationOrchestrator:
    def __init__(self, evaluators: List[BaseEvaluator], weights: Dict[str, float]):
        self.evaluators = evaluators
        self.weights = weights

    async def evaluate_all(self, **kwargs) -> Dict[str, Any]:
        logger.info("[EvaluationOrchestrator] Starting evaluation orchestration")
        
        all_scores = {}
        all_details = {}
        
        tasks = []
        for evaluator in self.evaluators:
            tasks.append(evaluator.evaluate(**kwargs))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"[EvaluationOrchestrator] Evaluator {i} failed: {str(result)}")
                continue
            all_scores.update(result)
        
        expected_metrics = set(self.weights.keys())
        produced_metrics = set(all_scores.keys())
        missing_metrics = expected_metrics - produced_metrics
        
        for metric in missing_metrics:
            all_scores[metric] = 0.0
            logger.warning(f"[EvaluationOrchestrator] Metric '{metric}' failed, filling with 0.0")
        
        overall_score = self._calculate_overall_score(all_scores)
        
        logger.info(f"[EvaluationOrchestrator] All scores: {all_scores}, overall: {overall_score}")
        return {
            "scores": all_scores,
            "overall_score": overall_score,
            "details": all_details
        }

    def _calculate_overall_score(self, scores: Dict[str, float]) -> float:
        total = 0.0
        weight_sum = 0.0
        
        for metric, weight in self.weights.items():
            if metric in scores:
                total += scores[metric] * weight
                weight_sum += weight
        
        if weight_sum == 0:
            return 0.0
        
        return total / weight_sum

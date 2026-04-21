from typing import Dict, Any, List, Optional
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
        failed_metrics: List[str] = []
        
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
        failed_metrics = list(expected_metrics - produced_metrics)
        
        if failed_metrics:
            logger.warning(
                f"[EvaluationOrchestrator] Failed metrics: {failed_metrics}"
            )
        
        overall_score = self._calculate_overall_score(all_scores, failed_metrics)
        
        logger.info(f"[EvaluationOrchestrator] All scores: {all_scores}, overall: {overall_score}, failed_metrics: {failed_metrics}")
        return {
            "scores": all_scores,
            "overall_score": overall_score,
            "details": all_details,
            "failed_metrics": failed_metrics
        }

    def _calculate_overall_score(
        self,
        scores: Dict[str, float],
        failed_metrics: Optional[List[str]] = None
    ) -> float:
        failed_set = set(failed_metrics) if failed_metrics else set()
        
        total = 0.0
        weight_sum = 0.0
        
        for metric, weight in self.weights.items():
            if metric in failed_set:
                continue
            if metric in scores and scores[metric] is not None:
                total += scores[metric] * weight
                weight_sum += weight
        
        if weight_sum == 0:
            return 0.0
        
        return total / weight_sum

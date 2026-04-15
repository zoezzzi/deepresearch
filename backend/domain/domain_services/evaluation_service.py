from typing import List, Dict, Any, Optional
import uuid
from domain.entities.evaluation_result import EvaluationResult
from domain.value_objects.workflow_id import WorkflowId
from domain.value_objects.evaluation_score import EvaluationScore
from domain.value_objects.evaluation_status import EvaluationStatus
from domain.repositories.evaluation_repository import EvaluationRepository
from common.logger import logger


class EvaluationService:
    def __init__(self, evaluation_repository: EvaluationRepository):
        self.evaluation_repository = evaluation_repository

    async def create_evaluation(self, workflow_id: WorkflowId) -> EvaluationResult:
        logger.info(f"[EvaluationService] Creating evaluation for workflow: {workflow_id.value}")
        
        evaluation_id = str(uuid.uuid4())
        evaluation = EvaluationResult(
            evaluation_id=evaluation_id,
            workflow_id=workflow_id,
            status=EvaluationStatus.PENDING
        )
        
        await self.evaluation_repository.save(evaluation)
        logger.info(f"[EvaluationService] Evaluation created: {evaluation_id}")
        return evaluation

    async def start_evaluation(self, evaluation_id: str) -> EvaluationResult:
        logger.info(f"[EvaluationService] Starting evaluation: {evaluation_id}")
        
        evaluation = await self.evaluation_repository.find_by_id(evaluation_id)
        if not evaluation:
            raise ValueError(f"Evaluation not found: {evaluation_id}")
        
        evaluation.start()
        await self.evaluation_repository.update(evaluation)
        return evaluation

    async def complete_evaluation(
        self,
        evaluation_id: str,
        scores: Dict[str, float],
        details: Optional[Dict[str, Any]] = None
    ) -> EvaluationResult:
        logger.info(f"[EvaluationService] Completing evaluation: {evaluation_id}")
        
        evaluation = await self.evaluation_repository.find_by_id(evaluation_id)
        if not evaluation:
            raise ValueError(f"Evaluation not found: {evaluation_id}")
        
        evaluation.complete(
            faithfulness=EvaluationScore(scores["faithfulness"]),
            context_relevancy=EvaluationScore(scores["context_relevancy"]),
            coverage=EvaluationScore(scores["coverage"]),
            structure=EvaluationScore(scores["structure"]),
            professional_depth=EvaluationScore(scores["professional_depth"]),
            overall_score=EvaluationScore(scores["overall_score"]),
            evaluation_details=details
        )
        
        await self.evaluation_repository.update(evaluation)
        logger.info(f"[EvaluationService] Evaluation completed: {evaluation_id}")
        return evaluation

    async def fail_evaluation(self, evaluation_id: str, error_message: str) -> EvaluationResult:
        logger.error(f"[EvaluationService] Failing evaluation: {evaluation_id}, error: {error_message}")
        
        evaluation = await self.evaluation_repository.find_by_id(evaluation_id)
        if not evaluation:
            raise ValueError(f"Evaluation not found: {evaluation_id}")
        
        evaluation.fail(error_message)
        await self.evaluation_repository.update(evaluation)
        return evaluation

    async def get_evaluation_by_workflow(self, workflow_id: str) -> List[EvaluationResult]:
        return await self.evaluation_repository.find_by_workflow_id(workflow_id)

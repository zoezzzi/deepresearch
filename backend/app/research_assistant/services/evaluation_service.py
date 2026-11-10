import uuid
from typing import Any

from app.research_assistant.models.models import EvaluationResult
from app.research_assistant.repositories import EvaluationRepository
from harness.logger import logger


class EvaluationService:
    def __init__(self, evaluation_repository: EvaluationRepository):
        self.evaluation_repository = evaluation_repository

    async def create_evaluation(
        self, workflow_id: str, scenario_id: str | None = None
    ) -> EvaluationResult:
        logger.info(
            f"[EvaluationService] Creating evaluation for workflow: {workflow_id}, scenario: {scenario_id}"
        )

        evaluation_id = str(uuid.uuid4())
        evaluation = EvaluationResult(
            evaluation_id=evaluation_id, workflow_id=workflow_id, scenario_id=scenario_id
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
        scores: dict[str, float],
        overall_score: float,
        details: dict[str, Any] | None = None,
    ) -> EvaluationResult:
        logger.info(f"[EvaluationService] Completing evaluation: {evaluation_id}")

        evaluation = await self.evaluation_repository.find_by_id(evaluation_id)
        if not evaluation:
            raise ValueError(f"Evaluation not found: {evaluation_id}")

        evaluation.complete(metrics=scores, overall_score=overall_score, evaluation_details=details)

        await self.evaluation_repository.update(evaluation)
        logger.info(f"[EvaluationService] Evaluation completed: {evaluation_id}")
        return evaluation

    async def fail_evaluation(self, evaluation_id: str, error_message: str) -> EvaluationResult:
        logger.error(
            f"[EvaluationService] Failing evaluation: {evaluation_id}, error: {error_message}"
        )

        evaluation = await self.evaluation_repository.find_by_id(evaluation_id)
        if not evaluation:
            raise ValueError(f"Evaluation not found: {evaluation_id}")

        evaluation.fail(error_message)
        await self.evaluation_repository.update(evaluation)
        return evaluation

    async def get_evaluation_by_workflow(self, workflow_id: str) -> list[EvaluationResult]:
        return await self.evaluation_repository.find_by_workflow_id(workflow_id)

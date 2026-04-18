from typing import List, Optional
from app.research_assistant.services import EvaluationService
from harness.evaluation.orchestrator import EvaluationOrchestrator
from harness.logger import logger


async def run_evaluation_task(
    evaluation_id: str,
    workflow_id: str,
    report: str,
    contexts: List[str],
    question: str,
    sub_questions: List[str],
    citations: List[str],
    evaluation_service: EvaluationService,
    evaluation_orchestrator: EvaluationOrchestrator
) -> None:
    logger.info(f"[EvaluationTask] Starting evaluation task: {evaluation_id}")

    try:
        await evaluation_service.start_evaluation(evaluation_id)

        result = await evaluation_orchestrator.evaluate_all(
            report=report,
            contexts=contexts,
            question=question,
            sub_questions=sub_questions,
            citations=citations
        )

        await evaluation_service.complete_evaluation(
            evaluation_id=evaluation_id,
            scores=result["scores"],
            details=result.get("details")
        )

        logger.info(f"[EvaluationTask] Evaluation completed successfully: {evaluation_id}")

    except Exception as e:
        logger.error(f"[EvaluationTask] Evaluation failed: {evaluation_id}, error: {str(e)}")
        try:
            await evaluation_service.fail_evaluation(evaluation_id, str(e))
        except Exception as fail_error:
            logger.error(f"[EvaluationTask] Failed to mark evaluation as failed: {str(fail_error)}")

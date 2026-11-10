from app.dev_survey.services import EvaluationService
from harness.evaluation.orchestrator import EvaluationOrchestrator
from harness.logger import logger


async def run_evaluation_task(
    evaluation_id: str,
    workflow_id: str,
    report: str,
    contexts: list[str],
    question: str,
    sub_questions: list[str] | None = None,
    checklist_items: list[str] | None = None,
    retrieved_documents: list[dict] | None = None,
    citations: list[str] | None = None,
    evaluation_service: EvaluationService = None,
    evaluation_orchestrator: EvaluationOrchestrator = None,
) -> None:
    logger.info(f"[EvaluationTask] Starting evaluation task: {evaluation_id}")

    try:
        await evaluation_service.start_evaluation(evaluation_id)

        result = await evaluation_orchestrator.evaluate_all(
            answer=report,
            report=report,
            contexts=contexts,
            question=question,
            sub_questions=sub_questions,
            checklist_items=checklist_items,
            retrieved_documents=retrieved_documents,
            citations=citations,
        )

        await evaluation_service.complete_evaluation(
            evaluation_id=evaluation_id,
            scores=result["scores"],
            overall_score=result["overall_score"],
            details=result.get("details"),
        )

        logger.info(f"[EvaluationTask] Evaluation completed successfully: {evaluation_id}")

    except Exception as e:
        logger.error(f"[EvaluationTask] Evaluation failed: {evaluation_id}, error: {str(e)}")
        try:
            await evaluation_service.fail_evaluation(evaluation_id, str(e))
        except Exception as fail_error:
            logger.error(f"[EvaluationTask] Failed to mark evaluation as failed: {str(fail_error)}")

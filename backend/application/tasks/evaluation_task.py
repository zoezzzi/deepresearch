from typing import List, Optional
from domain.value_objects.workflow_id import WorkflowId
from domain.domain_services.evaluation_service import EvaluationService
from infrastructure.evaluation.orchestrator import EvaluationOrchestrator
from common.logger import logger


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
    """
    异步执行评估任务
    
    Args:
        evaluation_id: 评估 ID
        workflow_id: 工作流 ID
        report: 报告内容
        contexts: 检索到的上下文片段
        question: 用户查询
        sub_questions: 子问题列表
        citations: 引用列表
        evaluation_service: 评估领域服务
        evaluation_orchestrator: 评估编排器
    """
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

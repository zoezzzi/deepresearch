from datetime import datetime
from typing import Optional, Dict, Any
from domain.value_objects.workflow_id import WorkflowId
from domain.value_objects.evaluation_score import EvaluationScore
from domain.value_objects.evaluation_status import EvaluationStatus
from common.utils.time_utils import get_current_utc_time


class EvaluationResult:
    def __init__(
        self,
        evaluation_id: str,
        workflow_id: WorkflowId,
        status: EvaluationStatus = EvaluationStatus.PENDING,
        faithfulness: Optional[EvaluationScore] = None,
        context_relevancy: Optional[EvaluationScore] = None,
        coverage: Optional[EvaluationScore] = None,
        structure: Optional[EvaluationScore] = None,
        professional_depth: Optional[EvaluationScore] = None,
        overall_score: Optional[EvaluationScore] = None,
        error_message: Optional[str] = None,
        evaluation_details: Optional[Dict[str, Any]] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ):
        self.evaluation_id = evaluation_id
        self.workflow_id = workflow_id
        self.status = status
        self.faithfulness = faithfulness
        self.context_relevancy = context_relevancy
        self.coverage = coverage
        self.structure = structure
        self.professional_depth = professional_depth
        self.overall_score = overall_score
        self.error_message = error_message
        self.evaluation_details = evaluation_details
        self.started_at = started_at
        self.completed_at = completed_at
        self.created_at = created_at or get_current_utc_time()
        self.updated_at = updated_at or get_current_utc_time()

    def start(self) -> None:
        self.status = EvaluationStatus.IN_PROGRESS
        self.started_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    def complete(
        self,
        faithfulness: EvaluationScore,
        context_relevancy: EvaluationScore,
        coverage: EvaluationScore,
        structure: EvaluationScore,
        professional_depth: EvaluationScore,
        overall_score: EvaluationScore,
        evaluation_details: Optional[Dict[str, Any]] = None
    ) -> None:
        self.status = EvaluationStatus.COMPLETED
        self.faithfulness = faithfulness
        self.context_relevancy = context_relevancy
        self.coverage = coverage
        self.structure = structure
        self.professional_depth = professional_depth
        self.overall_score = overall_score
        self.evaluation_details = evaluation_details
        self.completed_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

    def fail(self, error_message: str) -> None:
        self.status = EvaluationStatus.FAILED
        self.error_message = error_message
        self.completed_at = get_current_utc_time()
        self.updated_at = get_current_utc_time()

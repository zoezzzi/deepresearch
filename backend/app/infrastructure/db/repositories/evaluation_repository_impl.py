from typing import Optional, List
from sqlalchemy.orm import Session
from app.research_assistant.repositories import EvaluationRepository
from app.research_assistant.models.models import EvaluationResult
from app.research_assistant.models.enums import EvaluationStatus
from app.infrastructure.db.models import EvaluationModel
from harness.logger import logger


class EvaluationRepositoryImpl(EvaluationRepository):
    def __init__(self, db_session: Session):
        self.db_session = db_session

    def _to_domain_entity(self, model: EvaluationModel) -> EvaluationResult:
        return EvaluationResult(
            evaluation_id=model.evaluation_id,
            workflow_id=model.workflow_id,
            status=EvaluationStatus(model.status) if isinstance(model.status, str) else model.status,
            faithfulness=model.faithfulness,
            context_relevancy=model.context_relevancy,
            coverage=model.coverage,
            structure=model.structure,
            professional_depth=model.professional_depth,
            overall_score=model.overall_score,
            error_message=model.error_message,
            evaluation_details=model.evaluation_details,
            started_at=model.started_at,
            completed_at=model.completed_at,
            created_at=model.created_at,
            updated_at=model.updated_at
        )

    def _to_persistence_model(self, evaluation: EvaluationResult) -> EvaluationModel:
        return EvaluationModel(
            evaluation_id=evaluation.evaluation_id,
            workflow_id=evaluation.workflow_id,
            status=evaluation.status,
            faithfulness=evaluation.faithfulness,
            context_relevancy=evaluation.context_relevancy,
            coverage=evaluation.coverage,
            structure=evaluation.structure,
            professional_depth=evaluation.professional_depth,
            overall_score=evaluation.overall_score,
            error_message=evaluation.error_message,
            evaluation_details=evaluation.evaluation_details,
            started_at=evaluation.started_at,
            completed_at=evaluation.completed_at,
            created_at=evaluation.created_at,
            updated_at=evaluation.updated_at
        )

    async def save(self, evaluation: EvaluationResult) -> None:
        logger.info(f"[EvaluationRepositoryImpl] Saving evaluation: {evaluation.evaluation_id}")
        model = self._to_persistence_model(evaluation)
        self.db_session.add(model)
        self.db_session.flush()
        self.db_session.commit()

    async def find_by_id(self, evaluation_id: str) -> Optional[EvaluationResult]:
        logger.info(f"[EvaluationRepositoryImpl] Finding evaluation by id: {evaluation_id}")
        model = self.db_session.query(EvaluationModel).filter_by(evaluation_id=evaluation_id).first()
        if not model:
            return None
        return self._to_domain_entity(model)

    async def find_by_workflow_id(self, workflow_id: str) -> List[EvaluationResult]:
        logger.info(f"[EvaluationRepositoryImpl] Finding evaluations by workflow id: {workflow_id}")
        models = self.db_session.query(EvaluationModel).filter_by(workflow_id=workflow_id).order_by(EvaluationModel.created_at.desc()).all()
        return [self._to_domain_entity(model) for model in models]

    async def update(self, evaluation: EvaluationResult) -> None:
        logger.info(f"[EvaluationRepositoryImpl] Updating evaluation: {evaluation.evaluation_id}")
        model = self.db_session.query(EvaluationModel).filter_by(evaluation_id=evaluation.evaluation_id).first()
        if model:
            model.status = evaluation.status
            model.faithfulness = evaluation.faithfulness
            model.context_relevancy = evaluation.context_relevancy
            model.coverage = evaluation.coverage
            model.structure = evaluation.structure
            model.professional_depth = evaluation.professional_depth
            model.overall_score = evaluation.overall_score
            model.error_message = evaluation.error_message
            model.evaluation_details = evaluation.evaluation_details
            model.started_at = evaluation.started_at
            model.completed_at = evaluation.completed_at
            model.updated_at = evaluation.updated_at
            self.db_session.flush()
            self.db_session.commit()

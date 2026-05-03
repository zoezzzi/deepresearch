from typing import Optional, List
from sqlalchemy.orm import Session
from app.research_assistant.repositories import EvaluationRepository
from app.research_assistant.models.models import EvaluationResult
from app.research_assistant.models.enums import EvaluationStatus
from app.infrastructure.db.models import EvaluationModel
from app.infrastructure.db.session import with_db_retry
from harness.logger import logger


class EvaluationRepositoryImpl(EvaluationRepository):
    """
    EvaluationResult 持久化仓储实现

    事务管理策略：
    - 写操作（save/update）：flush() 将变更写入 DB → commit() 提交事务
    - 读操作（find_by_*）：查询后 commit() 关闭隐式读事务
      → 确保读、写之间事务被正确关闭，防止 idle-in-transaction 超时
    """

    def __init__(self, db_session: Session):
        self.db_session = db_session

    def _to_domain_entity(self, model: EvaluationModel) -> EvaluationResult:
        return EvaluationResult(
            evaluation_id=model.evaluation_id,
            workflow_id=model.workflow_id,
            scenario_id=model.scenario_id,
            status=EvaluationStatus(model.status) if isinstance(model.status, str) else model.status,
            metrics=model.metrics or {},
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
            scenario_id=evaluation.scenario_id,
            status=evaluation.status,
            metrics=evaluation.metrics or {},
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

        @with_db_retry(max_attempts=3)
        def _save():
            self.db_session.add(model)
            self.db_session.flush()

        try:
            _save()
            self.db_session.commit()
        except Exception:
            self.db_session.rollback()
            raise

    async def find_by_id(self, evaluation_id: str) -> Optional[EvaluationResult]:
        logger.info(f"[EvaluationRepositoryImpl] Finding evaluation by id: {evaluation_id}")

        @with_db_retry(max_attempts=3)
        def _find():
            model = self.db_session.query(EvaluationModel).filter_by(evaluation_id=evaluation_id).first()
            if not model:
                return None
            return self._to_domain_entity(model)

        try:
            result = _find()
            self.db_session.commit()
            return result
        except Exception:
            self.db_session.rollback()
            raise

    async def find_by_workflow_id(self, workflow_id: str) -> List[EvaluationResult]:
        logger.info(f"[EvaluationRepositoryImpl] Finding evaluations by workflow id: {workflow_id}")

        @with_db_retry(max_attempts=3)
        def _find():
            models = self.db_session.query(EvaluationModel).filter_by(workflow_id=workflow_id).order_by(EvaluationModel.created_at.desc()).all()
            return [self._to_domain_entity(model) for model in models]

        try:
            result = _find()
            self.db_session.commit()
            return result
        except Exception:
            self.db_session.rollback()
            raise

    async def update(self, evaluation: EvaluationResult) -> None:
        logger.info(f"[EvaluationRepositoryImpl] Updating evaluation: {evaluation.evaluation_id}")

        @with_db_retry(max_attempts=3)
        def _update():
            model = self.db_session.query(EvaluationModel).filter_by(evaluation_id=evaluation.evaluation_id).first()
            if model:
                model.status = evaluation.status
                model.scenario_id = evaluation.scenario_id
                model.metrics = evaluation.metrics or {}
                model.overall_score = evaluation.overall_score
                model.error_message = evaluation.error_message
                model.evaluation_details = evaluation.evaluation_details
                model.started_at = evaluation.started_at
                model.completed_at = evaluation.completed_at
                model.updated_at = evaluation.updated_at
                self.db_session.flush()

        try:
            _update()
            self.db_session.commit()
        except Exception:
            self.db_session.rollback()
            raise

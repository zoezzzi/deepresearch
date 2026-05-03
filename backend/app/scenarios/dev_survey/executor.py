from uuid import UUID
from sqlalchemy.orm import Session

from app.scenarios.protocols import ScenarioExecutor, ScenarioMetadata, ScenarioUIConfig
from app.scenarios.dev_survey.config import (
    SCENARIO_ID,
    SCENARIO_NAME,
    SCENARIO_DESCRIPTION,
    SCENARIO_VERSION,
    SCENARIO_AUTHOR,
    SCENARIO_UI_CONFIG,
    REPORT_URL_PREFIX
)
from app.infrastructure.db.session import SessionLocal
from app.service_factory import create_dev_survey_service
from app.dev_survey.models.dtos import CreateResearchRequest


class DevSurveyExecutor(ScenarioExecutor):
    def __init__(self):
        self._metadata = ScenarioMetadata(
            scenario_id=SCENARIO_ID,
            name=SCENARIO_NAME,
            description=SCENARIO_DESCRIPTION,
            version=SCENARIO_VERSION,
            author=SCENARIO_AUTHOR,
            ui_config=ScenarioUIConfig(**SCENARIO_UI_CONFIG)
        )

    def get_metadata(self) -> ScenarioMetadata:
        return self._metadata

    def _get_db(self) -> Session:
        return SessionLocal()

    async def create_workflow(self, request: CreateResearchRequest) -> any:
        db = self._get_db()
        try:
            service = create_dev_survey_service(db, REPORT_URL_PREFIX)
            return await service.create_research_workflow(request)
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                db.close()
            except Exception:
                pass
    
    async def execute_workflow(self, workflow_id: UUID) -> None:
        db = self._get_db()
        try:
            service = create_dev_survey_service(db, REPORT_URL_PREFIX)
            await service.execute_research_workflow(workflow_id)
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                db.close()
            except Exception:
                pass
    
    async def get_workflow_status(self, workflow_id: UUID) -> any:
        db = self._get_db()
        try:
            service = create_dev_survey_service(db, REPORT_URL_PREFIX)
            return await service.get_workflow_status(workflow_id)
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                db.close()
            except Exception:
                pass
    
    async def get_report_content(self, workflow_id: UUID) -> str | None:
        db = self._get_db()
        try:
            service = create_dev_survey_service(db, REPORT_URL_PREFIX)
            return await service.get_report_content(workflow_id)
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                db.close()
            except Exception:
                pass
    
    def get_report_file_path(self, report_id: str) -> str | None:
        db = self._get_db()
        try:
            service = create_dev_survey_service(db, REPORT_URL_PREFIX)
            return service.get_report_file_path(report_id)
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                db.close()
            except Exception:
                pass

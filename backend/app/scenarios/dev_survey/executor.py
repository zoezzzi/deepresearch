from uuid import UUID

from sqlalchemy.orm import Session

from app.dev_survey.models.dtos import CreateResearchRequest
from app.scenarios.dev_survey.config import (
    REPORT_URL_PREFIX,
    SCENARIO_AUTHOR,
    SCENARIO_DESCRIPTION,
    SCENARIO_ID,
    SCENARIO_NAME,
    SCENARIO_UI_CONFIG,
    SCENARIO_VERSION,
)
from app.scenarios.protocols import ScenarioExecutor, ScenarioMetadata, ScenarioUIConfig
from app.service_factory import create_dev_survey_service
from harness.db.session import SessionLocal


class DevSurveyExecutor(ScenarioExecutor):
    """Dev-survey scenario adapter.

    Mirrors ResearchAssistantExecutor, but rolls back explicitly on error paths
    because dev-survey performs writes in more places and a failed transaction
    must be released promptly.
    """

    def __init__(self):
        self._metadata = ScenarioMetadata(
            scenario_id=SCENARIO_ID,
            name=SCENARIO_NAME,
            description=SCENARIO_DESCRIPTION,
            version=SCENARIO_VERSION,
            author=SCENARIO_AUTHOR,
            ui_config=ScenarioUIConfig(**SCENARIO_UI_CONFIG),
        )

    def get_metadata(self) -> ScenarioMetadata:
        return self._metadata

    def _get_db(self) -> Session:
        return SessionLocal()

    async def create_workflow(self, request: CreateResearchRequest) -> any:
        """Persist a new dev-survey workflow and return its initial snapshot."""
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
        """Run the dev-survey workflow; scheduled as a background task."""
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
        """Read the current dev-survey workflow snapshot."""
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
        """Load the dev-survey report markdown, or None if absent."""
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
        """Resolve the on-disk path of a dev-survey report file."""
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

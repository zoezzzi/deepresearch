from uuid import UUID

from sqlalchemy.orm import Session

from app.research_assistant.models.dtos import CreateResearchRequest
from app.scenarios.protocols import ScenarioExecutor, ScenarioMetadata, ScenarioUIConfig
from app.scenarios.research_assistant.config import (
    REPORT_URL_PREFIX,
    SCENARIO_AUTHOR,
    SCENARIO_DESCRIPTION,
    SCENARIO_ID,
    SCENARIO_NAME,
    SCENARIO_UI_CONFIG,
    SCENARIO_VERSION,
)
from app.service_factory import create_research_service
from harness.db.session import SessionLocal


class ResearchAssistantExecutor(ScenarioExecutor):
    """Research-assistant scenario adapter.

    Adapts the generic ``ScenarioExecutor`` contract to ``ResearchService``:
    every call opens its own database session and closes it in ``finally``, so
    sessions are never shared across requests.
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
        """Persist a new workflow record and return its initial snapshot."""
        db = self._get_db()
        try:
            service = create_research_service(db, REPORT_URL_PREFIX)
            return await service.create_research_workflow(request)
        finally:
            db.close()

    async def execute_workflow(self, workflow_id: UUID) -> None:
        """Run the workflow to completion; intended to be scheduled as a background task."""
        db = self._get_db()
        try:
            service = create_research_service(db, REPORT_URL_PREFIX)
            await service.execute_research_workflow(workflow_id)
        finally:
            db.close()

    async def get_workflow_status(self, workflow_id: UUID) -> any:
        """Read the current workflow snapshot including its tasks."""
        db = self._get_db()
        try:
            service = create_research_service(db, REPORT_URL_PREFIX)
            return await service.get_workflow_status(workflow_id)
        finally:
            db.close()

    async def get_report_content(self, workflow_id: UUID) -> str | None:
        """Load the report markdown for a workflow, or None if not generated yet."""
        db = self._get_db()
        try:
            service = create_research_service(db, REPORT_URL_PREFIX)
            return await service.get_report_content(workflow_id)
        finally:
            db.close()

    def get_report_file_path(self, report_id: str) -> str | None:
        """Resolve the on-disk path of a report file for direct download."""
        db = self._get_db()
        try:
            service = create_research_service(db, REPORT_URL_PREFIX)
            return service.get_report_file_path(report_id)
        finally:
            db.close()

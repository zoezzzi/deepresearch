"""Scenario extension protocol: the executor interface and its metadata models.

To add a scenario, implement ``ScenarioExecutor`` and register a factory in
``manager``; the API layer never needs to know the concrete business flow.
"""

from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel


class ScenarioUIConfig(BaseModel):
    """Frontend copy overrides; absent fields fall back to the frontend defaults."""

    navbar_title: str | None = None
    form_title: str | None = None
    topic_label: str | None = None
    topic_placeholder: str | None = None


class ScenarioMetadata(BaseModel):
    """Public scenario description used by the scenario-list endpoint and UI."""

    scenario_id: str
    name: str
    description: str
    version: str
    author: str | None = None
    ui_config: ScenarioUIConfig | None = None


class ScenarioExecutor(Protocol):
    """Executor contract the API layer depends on.

    Each method owns its database session and closes it; callers never manage
    the transaction boundary.
    """

    def get_metadata(self) -> ScenarioMetadata: ...

    async def create_workflow(self, request: Any) -> Any: ...

    async def execute_workflow(self, workflow_id: UUID) -> None: ...

    async def get_workflow_status(self, workflow_id: UUID) -> Any: ...

    async def get_report_content(self, workflow_id: UUID) -> str | None: ...

    def get_report_file_path(self, report_id: str) -> str | None: ...

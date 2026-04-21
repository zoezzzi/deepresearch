from typing import List, Dict, Any
from harness.agents.base import Agent
from harness.agents.template_renderer import TemplateRenderer
from harness.config import get_harness_settings
from harness.logger import logger
from app.dev_survey.prompts.plan_agent_prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

settings = get_harness_settings()


class PlanAgent(Agent):
    def __init__(self, llm_client):
        super().__init__("PlanAgent")
        self.llm_client = llm_client
        self.timeout = settings.LLM_TIMEOUT_PLAN

    async def execute(self, topic: str, description: str = "") -> List[Dict[str, Any]]:
        logger.info(f"[{self.name}] Generating research plan for topic: {topic}")

        renderer = TemplateRenderer()
        prompt = renderer.render(USER_PROMPT_TEMPLATE, topic=topic, description=description)

        try:
            response = await self.llm_client.chat([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ], timeout=self.timeout)

            tasks = self._parse_response(response, topic)
            logger.info(f"[{self.name}] Successfully generated {len(tasks)} tasks")
            return tasks
        except Exception as e:
            logger.error(f"[{self.name}] Failed to generate research plan: {str(e)}")
            raise

    def _parse_response(self, response: str, topic: str = "") -> List[Dict[str, Any]]:
        import json
        try:
            start_idx = response.find('[')
            end_idx = response.rfind(']') + 1
            if start_idx != -1 and end_idx != 0:
                json_str = response[start_idx:end_idx]
                tasks = json.loads(json_str)
                for i, task in enumerate(tasks):
                    if 'order' not in task:
                        task['order'] = i + 1
                return tasks
        except json.JSONDecodeError:
            pass

        return [
            {
                "title": f"Research {topic or 'topic'}",
                "intent": "Gather basic information about the topic",
                "query": topic or "topic",
                "order": 1
            }
        ]

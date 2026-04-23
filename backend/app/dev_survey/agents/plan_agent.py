import json
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
        prompt = renderer.render(
            USER_PROMPT_TEMPLATE, 
            topic=topic, 
            description=description,
            task_count=4
        )

        try:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]

            response = await self.llm_client.chat(messages, timeout=self.timeout)

            tasks = self._parse_response(response, topic)
            
            for task in tasks:
                if not self._validate_task_schema(task):
                    task['title'] = task.get('title') or f"Research {topic}"
                    task['intent'] = task.get('intent') or f"Gather information about {topic}"
                    task['query'] = task.get('query') or topic
                    task['order'] = task.get('order') or 1

            logger.info(f"[{self.name}] Successfully generated {len(tasks)} tasks")
            return tasks
        except Exception as e:
            logger.error(f"[{self.name}] Failed to generate research plan: {str(e)}")
            return [self._create_fallback_task(topic)]

    def _validate_task_schema(self, task: Dict[str, Any]) -> bool:
        required_fields = ['title', 'intent', 'query', 'order']
        return all(field in task and task[field] for field in required_fields)

    def _create_fallback_task(self, topic: str) -> Dict[str, Any]:
        return {
            "title": f"Research {topic}",
            "intent": f"Gather basic information about {topic}",
            "query": topic,
            "order": 1
        }

    def _parse_response(self, response: str, topic: str = "") -> List[Dict[str, Any]]:
        try:
            start_idx = response.find('[')
            end_idx = response.rfind(']') + 1
            if start_idx != -1 and end_idx != 0:
                json_str = response[start_idx:end_idx]
                tasks = json.loads(json_str)
                if not isinstance(tasks, list):
                    logger.warning(f"[{self.name}] Parsed JSON is not a list, using fallback")
                    return [self._create_fallback_task(topic)]
                valid_tasks = [t for t in tasks if isinstance(t, dict)]
                if not valid_tasks:
                    logger.warning(f"[{self.name}] No valid task dicts in parsed JSON, using fallback")
                    return [self._create_fallback_task(topic)]
                for i, task in enumerate(valid_tasks):
                    if 'order' not in task:
                        task['order'] = i + 1
                return valid_tasks
        except json.JSONDecodeError as e:
            logger.warning(f"[{self.name}] JSON decode error: {str(e)}")

        return [self._create_fallback_task(topic)]

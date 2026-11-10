from typing import Any

from harness.agents.base import Agent
from harness.logger import logger


class PlanAgent(Agent):
    def __init__(self, llm_client):
        super().__init__("PlanAgent")
        self.llm_client = llm_client

    async def execute(self, topic: str, description: str = "") -> list[dict[str, Any]]:
        logger.info(f"[{self.name}] Generating research plan for topic: {topic}")

        prompt = self._build_prompt(topic, description)

        try:
            response = await self.llm_client.chat(
                [
                    {
                        "role": "system",
                        "content": "You are a research planning expert. Generate a structured research plan with clear, actionable tasks.",
                    },
                    {"role": "user", "content": prompt},
                ]
            )

            tasks = self._parse_response(response, topic)
            logger.info(f"[{self.name}] Successfully generated {len(tasks)} tasks")
            return tasks
        except Exception as e:
            logger.error(f"[{self.name}] Failed to generate research plan: {str(e)}")
            raise

    def _build_prompt(self, topic: str, description: str) -> str:
        return f"""Generate a research plan for the following topic:

Topic: {topic}
Description: {description or "No additional description provided"}

Please generate a list of 3-5 research tasks. For each task, provide:
- title: A clear, concise title for the task
- intent: The purpose or goal of this task
- query: A specific search query to use for this task
- order: The sequence number (starting from 1)

Format your response as a valid JSON array of objects with these fields."""

    def _parse_response(self, response: str, topic: str = "") -> list[dict[str, Any]]:
        import json

        try:
            start_idx = response.find("[")
            end_idx = response.rfind("]") + 1
            if start_idx != -1 and end_idx != 0:
                json_str = response[start_idx:end_idx]
                tasks = json.loads(json_str)
                for i, task in enumerate(tasks):
                    if "order" not in task:
                        task["order"] = i + 1
                return tasks
        except json.JSONDecodeError:
            pass

        return [
            {
                "title": f"Research {topic or 'topic'}",
                "intent": "Gather basic information about the topic",
                "query": topic or "topic",
                "order": 1,
            }
        ]

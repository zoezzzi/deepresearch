"""
CriticAgent - 批判代理

职责：评估报告质量，发现研究缺口，提出改进建议
Phase 1 MVP: 仅检查覆盖完整性和分析深度
"""

import json
from typing import Any

from app.dev_survey.prompts.critic_agent_prompts import (
    CRITIC_SYSTEM_PROMPT,
    CRITIC_USER_PROMPT_TEMPLATE,
)
from harness.agents.base import Agent
from harness.agents.template_renderer import TemplateRenderer
from harness.config import get_harness_settings
from harness.logger import logger

settings = get_harness_settings()


class CriticAgent(Agent):
    def __init__(self, llm_client):
        super().__init__("CriticAgent")
        self.llm_client = llm_client
        self.timeout = settings.LLM_TIMEOUT_REPORT

    async def execute(
        self,
        topic: str,
        report_content: str,
        sub_questions: list[str] = None,
        tasks: list[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        logger.info(f"[{self.name}] Evaluating report quality for topic: {topic}")

        sub_questions_str = (
            "\n".join(f"- {q}" for q in (sub_questions or []))
            if sub_questions
            else "No sub-questions provided"
        )

        task_summaries_str = self._build_task_summaries(tasks or [])

        renderer = TemplateRenderer()
        user_prompt = renderer.render(
            CRITIC_USER_PROMPT_TEMPLATE,
            topic=topic,
            sub_questions=sub_questions_str,
            report_content=report_content[:8000],
            task_summaries=task_summaries_str,
        )

        messages = [
            {"role": "system", "content": CRITIC_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            response = await self.llm_client.chat(messages, timeout=self.timeout)
            result = self._parse_response(response)

            logger.info(
                f"[{self.name}] Evaluation complete: overall={result.get('overall_score')}, "
                f"gaps={len(result.get('gaps', []))}"
            )
            return result

        except Exception as e:
            logger.error(f"[{self.name}] Evaluation failed: {str(e)}")
            return self._fallback_result(str(e))

    def _build_task_summaries(self, tasks: list[dict[str, Any]]) -> str:
        if not tasks:
            return "No task summaries available"

        parts = []
        for task in sorted(tasks, key=lambda t: t.get("order", 0)):
            if task.get("status") != "completed":
                continue
            parts.append(
                f"### {task.get('title', 'Untitled')}\n"
                f"Intent: {task.get('intent', 'N/A')}\n"
                f"Query: {task.get('query', 'N/A')}\n"
            )
        return "\n".join(parts) if parts else "No completed task summaries"

    def _parse_response(self, response: str) -> dict[str, Any]:
        try:
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            result = json.loads(text)

            return {
                "overall_score": float(result.get("overall_score", 5.0)),
                "dimensions": result.get("dimensions", []),
                "gaps": result.get("gaps", []),
                "suggestions": result.get("suggestions", []),
            }
        except (json.JSONDecodeError, IndexError) as e:
            logger.warning(f"[{self.name}] Failed to parse JSON response: {str(e)}")
            return self._fallback_result("JSON parse error")

    def _fallback_result(self, error: str) -> dict[str, Any]:
        return {
            "overall_score": 5.0,
            "dimensions": [
                {"name": "Coverage Completeness", "score": 5, "reasoning": error},
                {"name": "Analysis Depth", "score": 5, "reasoning": error},
            ],
            "gaps": [],
            "suggestions": [f"Evaluation failed: {error}. Proceeding with current report."],
        }

    def has_critical_gaps(self, quality_report: dict[str, Any]) -> bool:
        gaps = quality_report.get("gaps", [])
        return any(g.get("severity") == "critical" for g in gaps)

    def needs_reflection(self, quality_report: dict[str, Any]) -> bool:
        overall = quality_report.get("overall_score", 0)
        if overall >= 8.0:
            return False
        return self.has_critical_gaps(quality_report) or overall < 6.0

    def extract_queries(self, quality_report: dict[str, Any]) -> list[dict[str, Any]]:
        gaps = quality_report.get("gaps", [])
        supplementary = []
        for gap in gaps:
            if gap.get("severity") in ("critical", "major"):
                supplementary.append(
                    {
                        "query": gap.get("suggested_query", ""),
                        "intent": gap.get("topic", ""),
                        "title": gap.get("topic", "Supplementary Search"),
                    }
                )
        return supplementary[:3]

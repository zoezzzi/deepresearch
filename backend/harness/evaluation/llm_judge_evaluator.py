import json
from typing import Any

from harness.logger import logger

from .base_evaluator import BaseEvaluator


class LLMJudgeEvaluator(BaseEvaluator):
    def __init__(self, llm_client):
        self.llm_client = llm_client

    async def evaluate(self, report: str, sub_questions: list[str], **kwargs) -> dict[str, float]:
        logger.info("[LLMJudgeEvaluator] Evaluating coverage and structure")

        scores = {}

        coverage_score = await self._calculate_coverage(report, sub_questions)
        scores["coverage"] = coverage_score

        structure_score = await self._calculate_structure(report)
        scores["structure"] = structure_score

        logger.info(f"[LLMJudgeEvaluator] Scores: {scores}")
        return scores

    async def _calculate_coverage(self, report: str, sub_questions: list[str]) -> float:
        if not sub_questions:
            return 1.0

        try:
            prompt = self._build_coverage_prompt(report, sub_questions)

            response = await self.llm_client.chat(
                [
                    {
                        "role": "system",
                        "content": "You are an expert evaluator. Analyze the report and determine which sub-questions are answered.",
                    },
                    {"role": "user", "content": prompt},
                ]
            )

            result = self._parse_json_response(response)
            if result and "covered" in result:
                covered_count = sum(1 for c in result["covered"] if c)
                return covered_count / len(sub_questions)
        except Exception as e:
            logger.error(f"[LLMJudgeEvaluator] Coverage calculation error: {str(e)}")

        return 0.7

    async def _calculate_structure(self, report: str) -> float:
        try:
            prompt = self._build_structure_prompt(report)

            response = await self.llm_client.chat(
                [
                    {
                        "role": "system",
                        "content": "You are an expert evaluator. Assess the structure completeness of the report.",
                    },
                    {"role": "user", "content": prompt},
                ]
            )

            result = self._parse_json_response(response)
            if result and "score" in result:
                raw_score = result["score"]
                return (raw_score - 1) / 4.0
        except Exception as e:
            logger.error(f"[LLMJudgeEvaluator] Structure calculation error: {str(e)}")

        return 0.6

    def _build_coverage_prompt(self, report: str, sub_questions: list[str]) -> str:
        return f"""Given the following report, determine if each sub-question is answered.

Sub-questions: {json.dumps(sub_questions, ensure_ascii=False)}

Report:
{report}

Output JSON format:
{{"covered": [true/false for each sub-question], "reason": "brief explanation"}}"""

    def _build_structure_prompt(self, report: str) -> str:
        return f"""Evaluate the structure completeness of the following report (1-5 scale):
- 5: Clear introduction, well-structured body sections, conclusion, logical flow
- 3: Basic structure but awkward transitions between sections
- 1: No structure, disorganized

Report:
{report}

Output JSON format:
{{"score": integer, "reason": "brief explanation"}}"""

    def _parse_json_response(self, response: str) -> dict[str, Any]:
        try:
            start_idx = response.find("{")
            end_idx = response.rfind("}") + 1
            if start_idx != -1 and end_idx != 0:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        return {}

"""
覆盖度与模板合规性评估器
- checklist_coverage（清单覆盖度）：继承原 Coverage，sub_questions → checklist_items
- template_compliance（模板合规性）：替代原 Structure
"""
import json
import re
from typing import Dict, Any, List

from harness.evaluation.base_evaluator import BaseEvaluator
from harness.evaluation.llm_judge_evaluator import LLMJudgeEvaluator
from harness.logger import logger

CHINESE_STOP_WORDS = frozenset(
    "的 与 和 及 等 了 在 是 对 于 从 到 为 中 分析 研究 调研 了解 探索".split()
)


class ComplianceEvaluator(BaseEvaluator):
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self._llm_judge = LLMJudgeEvaluator(llm_client)

    async def evaluate(self, **kwargs) -> Dict[str, float]:
        logger.info("[ComplianceEvaluator] Evaluating checklist coverage and template compliance")

        scores = {}

        report = kwargs.get("report", kwargs.get("answer", ""))
        checklist_items = kwargs.get("checklist_items", kwargs.get("sub_questions", []))

        try:
            scores["checklist_coverage"] = await self._evaluate_checklist_coverage(
                report,
                checklist_items
            )

            scores["template_compliance"] = await self._evaluate_template_compliance(
                report
            )

            logger.info(f"[ComplianceEvaluator] Scores: {scores}")
            return scores

        except Exception as e:
            logger.error(f"[ComplianceEvaluator] Error: {str(e)}, using fallback")
            return {
                "checklist_coverage": 0.0,
                "template_compliance": 0.0
            }

    async def _evaluate_checklist_coverage(
        self,
        report: str,
        checklist_items: List[str]
    ) -> float:
        if not checklist_items:
            return 0.0

        report_lower = report.lower()
        covered: List[bool] = [False] * len(checklist_items)

        for i, item in enumerate(checklist_items):
            item_lower = item.lower()

            if item_lower in report_lower:
                covered[i] = True
                continue

            keywords = self._extract_chinese_keywords(item)
            if keywords:
                matched = sum(1 for kw in keywords if kw in report_lower)
                if matched >= len(keywords) * 0.5:
                    covered[i] = True
                    continue

            bigram_score = self._ngram_match_score(item, report, n=2)
            trigram_score = self._ngram_match_score(item, report, n=3)
            if max(bigram_score, trigram_score) >= 0.5:
                covered[i] = True
                continue

        rule_based_coverage = sum(covered) / len(checklist_items)

        if rule_based_coverage < 0.3 and self.llm_client is not None:
            uncovered_items = [
                item for item, is_covered in zip(checklist_items, covered) if not is_covered
            ]
            if uncovered_items:
                try:
                    llm_results = await self._llm_semantic_coverage(report, uncovered_items)
                    llm_idx = 0
                    for i, is_covered in enumerate(covered):
                        if not is_covered:
                            if llm_idx < len(llm_results) and llm_results[llm_idx]:
                                covered[i] = True
                            llm_idx += 1
                except Exception as e:
                    logger.error(f"[ComplianceEvaluator] LLM semantic coverage error: {str(e)}")

        return sum(covered) / len(checklist_items)

    def _extract_chinese_keywords(self, text: str) -> List[str]:
        cleaned = re.sub(r'[^\u4e00-\u9fff]', '', text)
        if not cleaned:
            return []

        for stop_word in CHINESE_STOP_WORDS:
            cleaned = cleaned.replace(stop_word, '')

        keywords: List[str] = []
        for n in range(4, 1, -1):
            i = 0
            while i <= len(cleaned) - n:
                segment = cleaned[i:i + n]
                keywords.append(segment)
                i += n
            cleaned = cleaned[i:]

        remaining = re.sub(r'[^\u4e00-\u9fff]', '', cleaned)
        if len(remaining) >= 2:
            keywords.append(remaining)

        return [kw for kw in keywords if len(kw) >= 2]

    def _ngram_match_score(self, item: str, text: str, n: int = 2) -> float:
        item_chars = re.sub(r'\s+', '', item)
        text_chars = re.sub(r'\s+', '', text)

        if len(item_chars) < n:
            return 0.0

        item_ngrams = [item_chars[i:i + n] for i in range(len(item_chars) - n + 1)]
        if not item_ngrams:
            return 0.0

        matched = sum(1 for ng in item_ngrams if ng in text_chars)
        return matched / len(item_ngrams)

    async def _llm_semantic_coverage(self, report: str, uncovered_items: List[str]) -> List[bool]:
        if not uncovered_items:
            return []

        truncated_report = report[:3000] if len(report) > 3000 else report
        items_json = json.dumps(uncovered_items, ensure_ascii=False)

        prompt = (
            f"给定以下研究报告，判断每个待查项是否在报告中被语义覆盖（即报告内容是否讨论了该项的主题）。\n\n"
            f"待查项列表：{items_json}\n\n"
            f"报告内容：\n{truncated_report}\n\n"
            f'输出 JSON 格式：{{"covered": [true/false, ...]}}，'
            f"covered 数组长度必须与待查项列表长度一致。"
        )

        response = await self.llm_client.chat([
            {"role": "system", "content": "你是一位专业的报告内容评估专家，擅长判断报告是否涵盖了特定主题。"},
            {"role": "user", "content": prompt}
        ])

        result = self._parse_json_response(response)
        if result and "covered" in result and isinstance(result["covered"], list):
            covered_list = [bool(c) for c in result["covered"]]
            if len(covered_list) == len(uncovered_items):
                return covered_list
            logger.warning(
                f"[ComplianceEvaluator] LLM returned {len(covered_list)} results "
                f"but expected {len(uncovered_items)}, discarding"
            )

        return [False] * len(uncovered_items)

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        try:
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            if start_idx != -1 and end_idx != 0:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        return {}

    async def _evaluate_template_compliance(self, report: str) -> float:
        score = 0.0

        if not report:
            return 0.5

        has_headings = any(line.strip().startswith(("#", "##", "###")) for line in report.split("\n"))
        if has_headings:
            score += 0.3

        has_lists = any("- " in line or "* " in line or "1." in line for line in report.split("\n"))
        if has_lists:
            score += 0.2

        report_lower = report.lower()
        key_elements = ["总结", "结论", "建议", "参考", "引用", "reference", "summary", "conclusion"]
        has_key_elements = sum(1 for elem in key_elements if elem in report_lower) >= 2
        if has_key_elements:
            score += 0.2

        min_length = 500
        if len(report) >= min_length:
            score += 0.3

        return min(score, 1.0)

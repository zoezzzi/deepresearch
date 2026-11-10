"""
覆盖度与模板合规性评估器
- checklist_coverage（清单覆盖度）：继承原 Coverage，sub_questions → checklist_items
- template_compliance（模板合规性）：替代原 Structure
"""

import json
import re
from typing import Any

from harness.evaluation.base_evaluator import BaseEvaluator
from harness.evaluation.llm_judge_evaluator import LLMJudgeEvaluator
from harness.logger import logger

CHINESE_STOP_WORDS = frozenset(
    [
        "的",
        "与",
        "和",
        "及",
        "等",
        "了",
        "在",
        "是",
        "对",
        "于",
        "从",
        "到",
        "为",
        "中",
        "分析",
        "研究",
        "调研",
        "了解",
        "探索",
    ]
)


class ComplianceEvaluator(BaseEvaluator):
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self._llm_judge = LLMJudgeEvaluator(llm_client)

    async def evaluate(self, **kwargs) -> dict[str, float]:
        logger.info("[ComplianceEvaluator] Evaluating checklist coverage and template compliance")

        scores = {}

        report = kwargs.get("report", kwargs.get("answer", ""))
        checklist_items = kwargs.get("checklist_items", kwargs.get("sub_questions", []))

        try:
            scores["checklist_coverage"] = await self._evaluate_checklist_coverage(
                report, checklist_items
            )

            scores["template_compliance"] = await self._evaluate_template_compliance(report)

            scores["citation_coverage"] = self._evaluate_citation_coverage(report)

            logger.info(f"[ComplianceEvaluator] Scores: {scores}")
            return scores

        except Exception as e:
            logger.error(f"[ComplianceEvaluator] Error: {str(e)}, using fallback")
            return {"checklist_coverage": 0.0, "template_compliance": 0.0, "citation_coverage": 0.0}

    async def _evaluate_checklist_coverage(self, report: str, checklist_items: list[str]) -> float:
        if not checklist_items:
            return 0.0

        report_lower = report.lower()
        covered: list[bool] = [False] * len(checklist_items)

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

    def _extract_chinese_keywords(self, text: str) -> list[str]:
        cleaned = re.sub(r"[^\u4e00-\u9fff]", "", text)
        if not cleaned:
            return []

        for stop_word in CHINESE_STOP_WORDS:
            cleaned = cleaned.replace(stop_word, "")

        keywords: list[str] = []
        for n in range(4, 1, -1):
            i = 0
            while i <= len(cleaned) - n:
                segment = cleaned[i : i + n]
                keywords.append(segment)
                i += n
            cleaned = cleaned[i:]

        remaining = re.sub(r"[^\u4e00-\u9fff]", "", cleaned)
        if len(remaining) >= 2:
            keywords.append(remaining)

        return [kw for kw in keywords if len(kw) >= 2]

    def _ngram_match_score(self, item: str, text: str, n: int = 2) -> float:
        item_chars = re.sub(r"\s+", "", item)
        text_chars = re.sub(r"\s+", "", text)

        if len(item_chars) < n:
            return 0.0

        item_ngrams = [item_chars[i : i + n] for i in range(len(item_chars) - n + 1)]
        if not item_ngrams:
            return 0.0

        matched = sum(1 for ng in item_ngrams if ng in text_chars)
        return matched / len(item_ngrams)

    async def _llm_semantic_coverage(self, report: str, uncovered_items: list[str]) -> list[bool]:
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

        response = await self.llm_client.chat(
            [
                {
                    "role": "system",
                    "content": "你是一位专业的报告内容评估专家，擅长判断报告是否涵盖了特定主题。",
                },
                {"role": "user", "content": prompt},
            ]
        )

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

    async def _evaluate_template_compliance(self, report: str) -> float:
        if not report:
            return 0.0

        score = 0.0

        has_any_headings = any(
            line.strip().startswith(("#", "##", "###")) for line in report.split("\n")
        )
        if has_any_headings:
            score += 0.1

        has_any_lists = any(
            "- " in line or "* " in line or "1." in line for line in report.split("\n")
        )
        if has_any_lists:
            score += 0.1

        required_sections = [
            "执行摘要",
            "决策总结",
            "参考文献",
            "executive summary",
            "decision",
            "reference",
        ]
        heading_texts = [
            line.strip().lstrip("#").strip().lower()
            for line in report.split("\n")
            if line.strip().startswith("#")
        ]
        sections_found = sum(
            1
            for section in required_sections
            if any(section in heading for heading in heading_texts)
        )
        score += min(sections_found * 0.1, 0.3)

        has_table_rows, has_table_separator = self._has_markdown_table(report)
        if has_table_rows:
            score += 0.1
        if has_table_separator:
            score += 0.1

        report_len = len(report)
        if report_len >= 1000:
            score += 0.05
        if report_len >= 2000:
            score += 0.05
        if report_len >= 3000:
            score += 0.05

        if re.search(r"^# ", report, re.MULTILINE):
            score += 0.05
        if re.search(r"^## ", report, re.MULTILINE):
            score += 0.05
        if re.search(r"^### ", report, re.MULTILINE):
            score += 0.05

        return min(score, 1.0)

    def _evaluate_citation_coverage(self, report: str) -> float:
        if not report:
            return 0.0

        score = 0.0

        if re.search(r"https?://\S+", report):
            score += 0.3

        if re.search(r"\[\d+\]", report):
            score += 0.2

        attribution_keywords = ["来源", "引用", "参考", "出处", "source", "reference", "citation"]
        if any(kw in report.lower() for kw in attribution_keywords):
            score += 0.2

        reference_headings = ["参考", "引用", "reference"]
        heading_lines = [
            line.strip().lstrip("#").strip().lower()
            for line in report.split("\n")
            if line.strip().startswith("#")
        ]
        if any(rh in heading for rh in reference_headings for heading in heading_lines):
            score += 0.3

        return min(score, 1.0)

    def _has_markdown_table(self, report: str) -> tuple[bool, bool]:
        lines = report.split("\n")
        has_table_rows = any(line.count("|") >= 3 for line in lines)
        has_table_separator = any(
            "|" in line and bool(re.match(r"^[\s|:\-]+$", line.strip())) for line in lines
        )
        return (has_table_rows, has_table_separator)

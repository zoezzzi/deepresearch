"""
准确性与信源质量评估器
- technical_faithfulness（技术准确性）：沿用 RAGAS 并强化
- source_quality（信源质量）：新增规则评估器
"""

import re
from typing import Any

from harness.evaluation.base_evaluator import BaseEvaluator
from harness.evaluation.ragas_evaluator import RAGASEvaluator
from harness.logger import logger


class AccuracyEvaluator(BaseEvaluator):
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self._ragas_evaluator = RAGASEvaluator(llm_client)

    async def evaluate(self, **kwargs) -> dict[str, float]:
        logger.info("[AccuracyEvaluator] Evaluating technical faithfulness and source quality")

        answer = kwargs.get("answer", kwargs.get("report", ""))
        contexts = kwargs.get("contexts", [])
        question = kwargs.get("question", "")
        retrieved_documents = kwargs.get("retrieved_documents", [])

        try:
            ragas_scores = await self._ragas_evaluator.evaluate(
                answer=answer, contexts=contexts, question=question
            )

            faithfulness = ragas_scores.get("faithfulness", 0.0)
            if faithfulness == 0.0:
                logger.warning(
                    "[AccuracyEvaluator] RAGAS faithfulness is 0.0, trying rule-based evaluation"
                )
                faithfulness = self._evaluate_faithfulness_with_rules(answer, contexts)

            scores = {
                "technical_faithfulness": faithfulness,
                "source_quality": await self._evaluate_source_quality(
                    retrieved_documents, contexts
                ),
            }

            logger.info(f"[AccuracyEvaluator] Scores: {scores}")
            return scores

        except Exception as e:
            logger.error(f"[AccuracyEvaluator] Error: {str(e)}, trying rule-based evaluation")
            try:
                faithfulness = self._evaluate_faithfulness_with_rules(answer, contexts)
            except Exception as rule_error:
                logger.error(
                    f"[AccuracyEvaluator] Rule-based evaluation also failed: {str(rule_error)}"
                )
                faithfulness = 0.0
            return {"technical_faithfulness": faithfulness, "source_quality": 0.0}

    def _evaluate_faithfulness_with_rules(self, report: str, contexts: list[str]) -> float:
        score = 0.0

        has_urls = bool(re.search(r"https?://\S+", report))
        if has_urls:
            score += 0.3

        has_ref_markers = bool(re.search(r"\[\d+\]", report))
        if has_ref_markers:
            score += 0.2

        has_ref_keywords = any(kw in report for kw in ["来源", "引用", "参考"])
        if has_ref_keywords:
            score += 0.2

        if contexts:
            context_words = set()
            for ctx in contexts:
                context_words.update(re.findall(r"[\u4e00-\u9fff\w]+", ctx.lower()))

            report_words = set(re.findall(r"[\u4e00-\u9fff\w]+", report.lower()))

            if context_words:
                overlap_ratio = len(context_words & report_words) / len(context_words)
                if overlap_ratio >= 0.5:
                    score += 0.3
                elif overlap_ratio >= 0.3:
                    score += 0.2

        return min(score, 1.0)

    async def _evaluate_source_quality(
        self, retrieved_documents: list[dict[str, Any]], contexts: list[str]
    ) -> float:
        """
        评估信源质量
        规则：
        - 信源数量 >= 3 → +0.3
        - 有权威来源（.edu, .gov, etc.）→ +0.3
        - 信源多样性 → +0.2
        - 上下文内容长度合理 → +0.2
        """
        score = 0.0

        if not retrieved_documents and not contexts:
            return 0.5

        if len(contexts) >= 3:
            score += 0.3
        elif len(contexts) >= 2:
            score += 0.2
        elif len(contexts) >= 1:
            score += 0.1

        authoritative_sources = False
        for ctx in contexts:
            if any(domain in ctx.lower() for domain in [".edu", ".gov", ".org", "wikipedia"]):
                authoritative_sources = True
                break
        if authoritative_sources:
            score += 0.3

        if len(contexts) >= 2:
            score += 0.2

        avg_length = sum(len(ctx) for ctx in contexts) / len(contexts)
        if 200 <= avg_length <= 2000:
            score += 0.2

        return min(score, 1.0)

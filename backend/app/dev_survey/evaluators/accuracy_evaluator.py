"""
准确性与信源质量评估器
- technical_faithfulness（技术准确性）：沿用 RAGAS 并强化
- source_quality（信源质量）：新增规则评估器
"""
import re
from typing import Dict, Any, List, Optional
from harness.evaluation.base_evaluator import BaseEvaluator
from harness.evaluation.ragas_evaluator import RAGASEvaluator
from harness.logger import logger


class AccuracyEvaluator(BaseEvaluator):
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self._ragas_evaluator = RAGASEvaluator(llm_client)
    
    async def evaluate(self, **kwargs) -> Dict[str, float]:
        logger.info("[AccuracyEvaluator] Evaluating technical faithfulness and source quality")
        
        answer = kwargs.get("answer", kwargs.get("report", ""))
        contexts = kwargs.get("contexts", [])
        question = kwargs.get("question", "")
        retrieved_documents = kwargs.get("retrieved_documents", [])
        
        try:
            ragas_scores = await self._ragas_evaluator.evaluate(
                answer=answer,
                contexts=contexts,
                question=question
            )
            
            faithfulness = ragas_scores.get("faithfulness", 0.0)
            if faithfulness == 0.0:
                logger.warning("[AccuracyEvaluator] RAGAS faithfulness is 0.0, trying rule-based evaluation")
                faithfulness = self._evaluate_faithfulness_with_rules(answer, contexts)
            
            scores = {
                "technical_faithfulness": faithfulness,
                "source_quality": await self._evaluate_source_quality(
                    retrieved_documents,
                    contexts
                )
            }
            
            logger.info(f"[AccuracyEvaluator] Scores: {scores}")
            return scores
            
        except Exception as e:
            logger.error(f"[AccuracyEvaluator] Error: {str(e)}, trying rule-based evaluation")
            try:
                faithfulness = self._evaluate_faithfulness_with_rules(answer, contexts)
            except Exception as rule_error:
                logger.error(f"[AccuracyEvaluator] Rule-based evaluation also failed: {str(rule_error)}")
                faithfulness = 0.0
            return {
                "technical_faithfulness": faithfulness,
                "source_quality": 0.0
            }
    
    def _evaluate_faithfulness_with_rules(self, report: str, contexts: List[str]) -> float:
        score = 0.0
        
        hasUrls = bool(re.search(r'https?://\S+', report))
        if hasUrls:
            score += 0.3
        
        hasRefMarkers = bool(re.search(r'\[\d+\]', report))
        if hasRefMarkers:
            score += 0.2
        
        hasRefKeywords = any(kw in report for kw in ["来源", "引用", "参考"])
        if hasRefKeywords:
            score += 0.2
        
        if contexts:
            contextWords = set()
            for ctx in contexts:
                contextWords.update(re.findall(r'[\u4e00-\u9fff\w]+', ctx.lower()))
            
            reportWords = set(re.findall(r'[\u4e00-\u9fff\w]+', report.lower()))
            
            if contextWords:
                overlapRatio = len(contextWords & reportWords) / len(contextWords)
                if overlapRatio >= 0.5:
                    score += 0.3
                elif overlapRatio >= 0.3:
                    score += 0.2
        
        return min(score, 1.0)
    
    async def _evaluate_source_quality(
        self,
        retrieved_documents: List[Dict[str, Any]],
        contexts: List[str]
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

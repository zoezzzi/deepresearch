from typing import Dict, Any, List, Optional
import re
from .base_evaluator import BaseEvaluator
from common.logger import logger


class RuleBasedEvaluator(BaseEvaluator):
    def __init__(self):
        self.term_list = [
            "algorithm", "architecture", "framework", "model", "system", "method",
            "approach", "technique", "protocol", "standard",
            "分析", "架构", "算法", "模型", "框架", "系统",
            "方法", "技术", "协议", "标准", "机制", "策略"
        ]

    async def evaluate(
        self,
        report: str,
        citations: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[str, float]:
        logger.info("[RuleBasedEvaluator] Evaluating professional depth")
        
        citations = citations or []
        depth_score = self._calculate_professional_depth(report, citations)
        
        logger.info(f"[RuleBasedEvaluator] Professional depth score: {depth_score}")
        return {"professional_depth": depth_score}

    def _calculate_professional_depth(self, report: str, citations: List[str]) -> float:
        words = self._split_words(report)
        total_words = len(words)
        
        if total_words == 0:
            return 0.5
        
        term_density = self._calculate_term_density(words)
        citation_density = self._calculate_citation_density(citations, total_words)
        
        term_score = min(term_density / 0.05, 1.0)
        citation_score = min(citation_density / 0.01, 1.0)
        
        return 0.5 * term_score + 0.5 * citation_score

    def _split_words(self, text: str) -> List[str]:
        cleaned = re.sub(r'[^\w\s]', ' ', text)
        words = cleaned.split()
        return [w.lower() for w in words]

    def _calculate_term_density(self, words: List[str]) -> float:
        if not words:
            return 0.0
        term_count = sum(1 for word in words if word in self.term_list)
        return term_count / len(words)

    def _calculate_citation_density(self, citations: List[str], total_words: int) -> float:
        if total_words == 0:
            return 0.0
        return len(citations) / total_words

from typing import Dict, Any, List
from .base_evaluator import BaseEvaluator
from harness.logger import logger

try:
    from ragas.metrics import faithfulness, context_relevancy
    from ragas.llms import LangchainLLMWrapper
    RAGAS_AVAILABLE = True
except ImportError:
    RAGAS_AVAILABLE = False
    logger.warning("RAGAS not available, will use fallback implementations")


class RAGASEvaluator(BaseEvaluator):
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self._ragas_available = RAGAS_AVAILABLE

    async def evaluate(
        self,
        answer: str,
        contexts: List[str],
        question: str,
        **kwargs
    ) -> Dict[str, float]:
        logger.info("[RAGASEvaluator] Evaluating faithfulness and context relevancy")
        
        if not self._ragas_available:
            return await self._fallback_evaluate(answer, contexts, question)
        
        try:
            scores = {}
            
            faithfulness_score = await self._evaluate_faithfulness(answer, contexts)
            scores["faithfulness"] = faithfulness_score
            
            relevancy_score = await self._evaluate_context_relevancy(question, contexts)
            scores["context_relevancy"] = relevancy_score
            
            logger.info(f"[RAGASEvaluator] Scores: {scores}")
            return scores
        except Exception as e:
            logger.error(f"[RAGASEvaluator] Error using RAGAS: {str(e)}, falling back")
            return await self._fallback_evaluate(answer, contexts, question)

    async def _evaluate_faithfulness(self, answer: str, contexts: List[str]) -> float:
        if not self._ragas_available:
            logger.warning("[RAGASEvaluator] RAGAS unavailable, faithfulness evaluation failed")
            return 0.0
        try:
            score = await faithfulness.ascore(answer=answer, contexts=contexts)
            if score is None:
                logger.warning("[RAGASEvaluator] Faithfulness score is None, evaluation failed")
                return 0.0
            return float(score)
        except Exception as e:
            logger.warning(f"[RAGASEvaluator] Faithfulness evaluation failed: {str(e)}")
            return 0.0

    async def _evaluate_context_relevancy(self, question: str, contexts: List[str]) -> float:
        if not self._ragas_available:
            logger.warning("[RAGASEvaluator] RAGAS unavailable, context_relevancy evaluation failed")
            return 0.0
        try:
            score = await context_relevancy.ascore(question=question, contexts=contexts)
            if score is None:
                logger.warning("[RAGASEvaluator] Context relevancy score is None, evaluation failed")
                return 0.0
            return float(score)
        except Exception as e:
            logger.warning(f"[RAGASEvaluator] Context relevancy evaluation failed: {str(e)}")
            return 0.0

    async def _fallback_evaluate(
        self,
        answer: str,
        contexts: List[str],
        question: str
    ) -> Dict[str, float]:
        logger.warning("[RAGASEvaluator] Fallback evaluation used, all scores set to 0.0 due to evaluation failure")
        return {
            "faithfulness": 0.0,
            "context_relevancy": 0.0
        }

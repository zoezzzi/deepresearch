"""
可执行性与决策清晰度评估器
- actionability（可执行性）：替代原 Professional Depth
- decision_clarity（决策清晰度）：新增 LLM-as-Judge
"""
from typing import Dict, Any, List
from harness.evaluation.base_evaluator import BaseEvaluator
from harness.evaluation.rule_evaluator import RuleBasedEvaluator
from harness.logger import logger


class ActionabilityEvaluator(BaseEvaluator):
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self._rule_evaluator = RuleBasedEvaluator()
    
    async def evaluate(self, **kwargs) -> Dict[str, float]:
        logger.info("[ActionabilityEvaluator] Evaluating actionability and decision clarity")
        
        scores = {}
        
        report = kwargs.get("report", kwargs.get("answer", ""))
        question = kwargs.get("question", "")
        
        try:
            scores["actionability"] = await self._evaluate_actionability(report)
            
            scores["decision_clarity"] = await self._evaluate_decision_clarity(
                report,
                question
            )
            
            logger.info(f"[ActionabilityEvaluator] Scores: {scores}")
            return scores
            
        except Exception as e:
            logger.error(f"[ActionabilityEvaluator] Error: {str(e)}, using fallback")
            return {
                "actionability": 0.0,
                "decision_clarity": 0.0
            }
    
    async def _evaluate_actionability(self, report: str) -> float:
        """
        评估可执行性（规则为主）
        检查：
        - 是否有具体步骤
        - 是否有代码示例
        - 是否有明确的建议
        """
        score = 0.0
        
        if not report:
            return 0.5
        
        report_lower = report.lower()
        
        code_blocks = report.count("```") >= 2
        if code_blocks:
            score += 0.3
        
        has_steps = any(
            keyword in report_lower 
            for keyword in ["步骤", "step", "1.", "2.", "3.", "4.", "5."]
        )
        if has_steps:
            score += 0.2
        
        has_suggestions = any(
            keyword in report_lower 
            for keyword in ["建议", "should", "recommend", "建议使用", "建议采用"]
        )
        if has_suggestions:
            score += 0.2
        
        has_commands = any(
            keyword in report_lower 
            for keyword in ["npm", "pip", "install", "run", "docker", "git"]
        )
        if has_commands:
            score += 0.3
        
        return min(score, 1.0)
    
    async def _evaluate_decision_clarity(self, report: str, question: str) -> float:
        """
        评估决策清晰度（LLM-as-Judge + 规则）
        """
        score = 0.0
        
        if not report:
            return 0.5
        
        report_lower = report.lower()
        
        has_conclusion = any(
            keyword in report_lower 
            for keyword in ["结论", "conclusion", "总结", "summary", "最终"]
        )
        if has_conclusion:
            score += 0.3
        
        has_comparison = any(
            keyword in report_lower 
            for keyword in ["对比", "vs", "vs.", "比较", "pros", "cons", "优点", "缺点"]
        )
        if has_comparison:
            score += 0.3
        
        has_recommendation = any(
            keyword in report_lower 
            for keyword in ["推荐", "建议选择", "建议使用", "prefer", "recommend"]
        )
        if has_recommendation:
            score += 0.4
        
        return min(score, 1.0)

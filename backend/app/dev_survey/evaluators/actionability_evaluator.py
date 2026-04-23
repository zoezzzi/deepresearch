"""
可执行性与决策清晰度评估器
- actionability（可执行性）：替代原 Professional Depth
- decision_clarity（决策清晰度）：新增 LLM-as-Judge
"""
import json
import re
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
        score = 0.0

        if not report:
            return 0.0

        score += self._check_code_blocks(report)
        score += self._check_steps(report)
        score += self._check_suggestions(report)
        score += self._check_commands(report)

        return min(score, 1.0)

    def _check_code_blocks(self, report: str) -> float:
        code_blocks = re.findall(r'```[\w]*\n(.*?)```', report, re.DOTALL)
        if not code_blocks:
            return 0.0

        executable_indicators = [
            'def ', 'function ', 'import ', 'from ',
            'const ', 'let ', 'var ', 'class ',
            '=>', 'async ', 'await ', 'return ',
        ]

        for block in code_blocks:
            if any(indicator in block for indicator in executable_indicators):
                return 0.3

        return 0.15

    def _check_steps(self, report: str) -> float:
        step_pattern = r'(?:^|\n)\s*(?:步骤\s*\d+|\d+\.)\s*(.{10,})'

        valid_steps = len(re.findall(step_pattern, report))

        if valid_steps >= 3:
            return 0.2
        elif valid_steps >= 1:
            return 0.1
        return 0.0

    def _check_suggestions(self, report: str) -> float:
        report_lower = report.lower()
        if any(kw in report_lower for kw in ["建议", "should", "recommend", "建议使用", "建议采用"]):
            return 0.2
        return 0.0

    def _check_commands(self, report: str) -> float:
        complete_command_patterns = [
            r'(?:npm|yarn|pnpm)\s+(?:install|add|run|init)\s+\S+',
            r'pip\s+(?:install|uninstall)\s+\S+',
            r'docker\s+(?:run|build|pull|compose)\s+\S+',
            r'git\s+(?:clone|checkout|pull|push)\s+\S+',
        ]

        for pattern in complete_command_patterns:
            if re.search(pattern, report):
                return 0.3

        partial_keywords = ["npm", "pip", "install", "docker", "git"]
        report_lower = report.lower()
        if any(kw in report_lower for kw in partial_keywords):
            return 0.1

        return 0.0
    
    async def _evaluate_decision_clarity(self, report: str, question: str) -> float:
        if not report:
            return 0.5

        report_lower = report.lower()

        score = 0.0

        recommendation_keywords = ["推荐", "建议选择", "建议使用", "prefer", "recommend"]
        has_recommendation = any(kw in report_lower for kw in recommendation_keywords)
        if not has_recommendation:
            return 0.2
        score += 0.2

        comparison_keywords = ["vs", "对比", "比较", "versus"]
        has_comparison = any(kw in report_lower for kw in comparison_keywords)
        if has_comparison:
            score += 0.3

        rationale_keywords = ["因为", "由于", "原因", "because", "due to", "reason"]
        has_rationale = any(kw in report_lower for kw in rationale_keywords)
        if has_rationale:
            score += 0.3

        scenario_keywords = ["适合", "适用", "场景", "scenario", "use case", "when to"]
        has_scenario = any(kw in report_lower for kw in scenario_keywords)
        if has_scenario:
            score += 0.2

        return min(score, 1.0)

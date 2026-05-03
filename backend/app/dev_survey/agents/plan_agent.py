import json
from typing import List, Dict, Any
from harness.agents.base import Agent
from harness.agents.template_renderer import TemplateRenderer
from harness.config import get_harness_settings
from harness.logger import logger
from app.dev_survey.prompts.plan_agent_prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

settings = get_harness_settings()


class PlanAgent(Agent):
    def __init__(self, llm_client):
        super().__init__("PlanAgent")
        self.llm_client = llm_client
        self.timeout = settings.LLM_TIMEOUT_PLAN

    async def execute(self, topic: str, description: str = "") -> List[Dict[str, Any]]:
        logger.info(f"[{self.name}] Generating research plan for topic: {topic}")

        renderer = TemplateRenderer()
        prompt = renderer.render(
            USER_PROMPT_TEMPLATE, 
            topic=topic, 
            description=description,
            task_count=4
        )

        try:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]

            response = await self.llm_client.chat(messages, timeout=self.timeout)

            tasks = self._parse_response(response, topic)
            
            for task in tasks:
                if not self._validate_task_schema(task):
                    task['title'] = task.get('title') or f"Research {topic}"
                    task['intent'] = task.get('intent') or f"Gather information about {topic}"
                    task['query'] = task.get('query') or topic
                    task['order'] = task.get('order') or 1

            logger.info(f"[{self.name}] Successfully generated {len(tasks)} tasks")
            return tasks
        except Exception as e:
            logger.error(f"[{self.name}] Failed to generate research plan: {str(e)}")
            return [self._create_fallback_task(topic)]

    def _validate_task_schema(self, task: Dict[str, Any]) -> bool:
        required_fields = ['title', 'intent', 'query', 'order']
        has_required = all(field in task and task[field] for field in required_fields)
        if 'depends_on' not in task:
            task['depends_on'] = []
        if not isinstance(task.get('depends_on'), list):
            task['depends_on'] = []
        return has_required

    def _create_fallback_task(self, topic: str) -> Dict[str, Any]:
        return {
            "title": f"Research {topic}",
            "intent": f"Gather basic information about {topic}",
            "query": topic,
            "order": 1,
            "depends_on": []
        }

    def _parse_response(self, response: str, topic: str = "") -> List[Dict[str, Any]]:
        try:
            # Step 1: 清理 Markdown 代码块包裹
            cleaned_response = self._clean_markdown_response(response)
            
            # Step 2: 查找 JSON 数组边界
            start_idx = cleaned_response.find('[')
            end_idx = cleaned_response.rfind(']') + 1
            
            if start_idx != -1 and end_idx != 0:
                json_str = cleaned_response[start_idx:end_idx]
                
                # Step 3: 尝试标准 JSON 解析
                try:
                    tasks = json.loads(json_str)
                    if isinstance(tasks, list):
                        valid_tasks = [t for t in tasks if isinstance(t, dict)]
                        if valid_tasks:
                            for i, task in enumerate(valid_tasks):
                                if 'order' not in task:
                                    task['order'] = i + 1
                            logger.info(f"[{self.name}] Successfully parsed {len(valid_tasks)} tasks from JSON")
                            return valid_tasks
                except json.JSONDecodeError as e:
                    logger.warning(f"[{self.name}] Standard JSON decode failed: {str(e)}, trying relaxed parsing")
                
                # Step 4: 尝试宽松解析（修复常见格式问题）
                relaxed_json = self._fix_common_json_issues(json_str)
                try:
                    tasks = json.loads(relaxed_json)
                    if isinstance(tasks, list):
                        valid_tasks = [t for t in tasks if isinstance(t, dict)]
                        if valid_tasks:
                            for i, task in enumerate(valid_tasks):
                                if 'order' not in task:
                                    task['order'] = i + 1
                            logger.info(f"[{self.name}] Successfully parsed {len(valid_tasks)} tasks with relaxed parsing")
                            return valid_tasks
                except json.JSONDecodeError as e:
                    logger.warning(f"[{self.name}] Relaxed JSON decode also failed: {str(e)}")
            
            logger.warning(f"[{self.name}] No valid JSON array found, using fallback")
        except Exception as e:
            logger.warning(f"[{self.name}] Unexpected error during parsing: {str(e)}")

        return [self._create_fallback_task(topic)]
    
    def _clean_markdown_response(self, response: str) -> str:
        """清理 Markdown 代码块包裹"""
        cleaned = response.strip()
        
        # 移除 ```json 和 ``` 包裹
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:]
        if cleaned.startswith('```'):
            cleaned = cleaned[3:]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
        
        return cleaned.strip()
    
    def _fix_common_json_issues(self, json_str: str) -> str:
        """修复常见的 JSON 格式问题"""
        import re
        
        fixed = json_str.strip()
        
        # 1. 单引号转双引号
        fixed = fixed.replace("'", '"')
        
        # 2. 修复末尾多余的逗号
        fixed = re.sub(r',\s*([\]}])', r'\1', fixed)
        
        # 3. 修复对象中缺失的冒号（简单处理）
        # 例如：{key value} → {key: value}
        # 但这里只做最基础的修复
        
        # 4. 移除可能导致解析问题的控制字符
        fixed = re.sub(r'[\x00-\x1f\x7f]', '', fixed)
        
        # 5. 修复注释（JSON 标准不支持注释）
        # 移除 // ... 或 /* ... */ 注释
        
        return fixed

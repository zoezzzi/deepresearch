from difflib import SequenceMatcher

from app.dev_survey.prompts.summarizer_agent_prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from harness.agents.base import Agent
from harness.agents.template_renderer import TemplateRenderer
from harness.config import get_harness_settings
from harness.logger import logger

settings = get_harness_settings()


class SummarizerAgent(Agent):
    def __init__(self, llm_client):
        super().__init__("SummarizerAgent")
        self.llm_client = llm_client
        self.timeout = settings.LLM_TIMEOUT_EXECUTE

    async def execute(
        self, intent: str, search_results: list, accumulated_knowledge: list[str] | None = None
    ) -> tuple[str, str, str]:
        logger.info(f"[{self.name}] Summarizing search results for intent: {intent}")

        try:
            deduped_results = self._deduplicate_results(search_results)
            formatted_results = self._format_search_results(deduped_results, intent)

            renderer = TemplateRenderer()
            prompt = renderer.render(
                USER_PROMPT_TEMPLATE, intent=intent, formatted_results=formatted_results
            )

            # 只有当 accumulated_knowledge 不为 None 时，而且不是空列表时才添加知识传递的内容
            if accumulated_knowledge is not None and accumulated_knowledge:
                formatted_knowledge = "\n".join(
                    f"{i + 1}. {finding}" for i, finding in enumerate(accumulated_knowledge)
                )
                knowledge_context = (
                    f"前序任务的关键发现：\n{formatted_knowledge}\n\n"
                    f"请参考以上发现，避免重复搜索和矛盾结论。"
                )
                prompt = knowledge_context + "\n\n" + prompt

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]

            response = await self.llm_client.chat(messages, timeout=self.timeout)
            return self._parse_response(response, deduped_results)
        except Exception as e:
            logger.error(f"[{self.name}] Summarization failed: {str(e)}")
            return self._create_fallback_summary(search_results)

    def _format_search_results(self, search_results: list, intent: str = "") -> str:
        return "\n\n".join(
            [
                f"Source {i + 1}:\nTitle: {result.title}\nURL: {result.url}\nContent: {self._extract_relevant_paragraphs(result.content, intent)}"
                for i, result in enumerate(search_results[:5])
            ]
        )

    def _extract_relevant_paragraphs(
        self, content: str, intent: str, max_paragraphs: int = 3
    ) -> str:
        if not content:
            return ""

        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip() and len(p.strip()) > 50]

        if not paragraphs:
            return content[:500]

        intent_keywords = set(intent.lower().split())

        def score_paragraph(para: str) -> float:
            para_lower = para.lower()
            return sum(1 for kw in intent_keywords if kw in para_lower) / max(
                len(intent_keywords), 1
            )

        scored = [(score_paragraph(p), p) for p in paragraphs]
        scored.sort(key=lambda x: x[0], reverse=True)

        selected = []
        for score, para in scored[:max_paragraphs]:
            if len(para) > 300:
                para = para[:300] + "..."
            selected.append(para)

        return "\n\n".join(selected)

    def _deduplicate_results(self, results: list) -> list:
        if not results:
            return results

        seen_urls = set()
        url_deduped = []
        for r in results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                url_deduped.append(r)

        final_results = []
        for r in url_deduped:
            is_duplicate = False
            for existing in final_results:
                if len(r.content) > 100 and len(existing.content) > 100:
                    ratio = SequenceMatcher(None, r.content[:100], existing.content[:100]).ratio()
                    if ratio > 0.8:
                        is_duplicate = True
                        break
            if not is_duplicate:
                final_results.append(r)

        return final_results

    def _create_fallback_summary(self, search_results: list) -> tuple[str, str, str]:
        summary = "Unable to generate summary due to processing error."
        sources = (
            "\n".join([f"- {r.title}: {r.url}" for r in search_results[:5]])
            if search_results
            else "No sources available"
        )
        notices = "No notices available"
        return summary, sources, notices

    def _parse_response(self, response: str, search_results: list) -> tuple[str, str, str]:
        lines = response.split("\n")
        summary_parts = []
        sources_parts = []
        notices_parts = []

        current_section = None

        for line in lines:
            line_lower = line.lower()
            if "technical summary" in line_lower or "技术摘要" in line_lower:
                current_section = "summary"
            elif (
                "sources summary" in line_lower
                or "来源摘要" in line_lower
                or "社区与生态系统" in line_lower
            ):
                current_section = "sources"
            elif any(
                kw in line_lower
                for kw in ("pitfalls", "warnings", "best practices", "陷阱", "警告", "最佳实践")
            ):
                current_section = "notices"
            elif current_section == "summary":
                summary_parts.append(line)
            elif current_section == "sources":
                sources_parts.append(line)
            elif current_section == "notices":
                notices_parts.append(line)

        if not sources_parts:
            sources_parts = [f"- {result.title}: {result.url}" for result in search_results[:5]]

        summary_text = "\n".join(summary_parts).strip() or response[:500]
        sources_text = "\n".join(sources_parts).strip()
        notices_text = "\n".join(notices_parts).strip()

        if not sources_text:
            sources_text = "No sources available"
        if not notices_text:
            notices_text = "No notices"

        return summary_text, sources_text, notices_text

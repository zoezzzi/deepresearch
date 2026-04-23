from typing import List, Tuple


class ReportValidator:
    REQUIRED_SECTIONS = [
        ("执行摘要", ["executive summary", "摘要", "概述"]),
        ("决策总结", ["decision", "决策", "推荐", "建议"]),
        ("参考文献", ["reference", "参考", "引用", "来源"]),
    ]

    def validate(self, report: str) -> Tuple[bool, List[str]]:
        if not report:
            return False, ["报告为空"]

        missing = []
        headings = self._extract_headings(report)

        for section_name, aliases in self.REQUIRED_SECTIONS:
            if not self._has_section(headings, section_name, aliases):
                missing.append(section_name)

        return len(missing) == 0, missing

    def _extract_headings(self, report: str) -> List[str]:
        return [
            line.strip().lstrip('#').strip()
            for line in report.split('\n')
            if line.strip().startswith('#')
        ]

    def _has_section(self, headings: List[str], section_name: str, aliases: List[str]) -> bool:
        all_names = [section_name] + aliases
        for heading in headings:
            heading_lower = heading.lower()
            if any(name in heading_lower for name in all_names):
                return True
        return False

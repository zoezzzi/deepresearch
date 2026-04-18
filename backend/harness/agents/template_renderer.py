from typing import Dict, Any
from jinja2 import Template


class TemplateRenderer:
    def __init__(self):
        pass

    def render(self, template_str: str, **kwargs: Any) -> str:
        template = Template(template_str)
        return template.render(**kwargs)

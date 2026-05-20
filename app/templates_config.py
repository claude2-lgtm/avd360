import json
import os
from typing import Any, Dict
from jinja2 import Environment, FileSystemLoader
from starlette.responses import HTMLResponse


class Templates:
    def __init__(self, directory: str = "app/templates"):
        self.env = Environment(
            loader=FileSystemLoader(directory),
            autoescape=True,
        )
        self.env.cache = None
        self.env.filters['fromjson'] = lambda v: json.loads(v) if v else []

    def TemplateResponse(self, name: str, context: Dict[str, Any], status_code: int = 200):
        request = context.get("request")
        template = self.env.get_template(name)
        content = template.render(**context)
        return HTMLResponse(content=content, status_code=status_code)


def make_templates(directory: str = "app/templates") -> Templates:
    return Templates(directory)

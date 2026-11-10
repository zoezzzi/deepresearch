import json
from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class OutputEnforcer:
    def __init__(self):
        pass

    def enforce_json(self, text: str) -> dict[str, Any]:
        try:
            start_idx = text.find("{")
            end_idx = text.rfind("}") + 1
            if start_idx != -1 and end_idx != 0:
                json_str = text[start_idx:end_idx]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        return {}

    def enforce_json_array(self, text: str) -> list[dict[str, Any]]:
        try:
            start_idx = text.find("[")
            end_idx = text.rfind("]") + 1
            if start_idx != -1 and end_idx != 0:
                json_str = text[start_idx:end_idx]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        return []

    def enforce_model(self, text: str, model_class: type[T]) -> T | None:
        try:
            data = self.enforce_json(text)
            if data:
                return model_class(**data)
        except Exception:
            pass
        return None

    def enforce_model_list(self, text: str, model_class: type[T]) -> list[T]:
        try:
            data_list = self.enforce_json_array(text)
            return [model_class(**item) for item in data_list]
        except Exception:
            return []

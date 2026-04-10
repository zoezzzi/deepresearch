from dataclasses import dataclass


@dataclass(frozen=True)
class TaskSummary:
    value: str

    def __post_init__(self):
        if not isinstance(self.value, str) or not self.value or self.value.strip() == "":
            raise ValueError("TaskSummary must be a non-empty, non-whitespace string")

    def __str__(self) -> str:
        return self.value

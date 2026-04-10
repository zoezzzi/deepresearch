from dataclasses import dataclass


@dataclass(frozen=True)
class TaskId:
    value: str

    def __post_init__(self):
        if not self.value or not isinstance(self.value, str):
            raise ValueError("TaskId must be a non-empty string")

    def __str__(self) -> str:
        return self.value

from dataclasses import dataclass


@dataclass(frozen=True)
class TaskIntent:
    value: str

    def __post_init__(self):
        if not self.value or not isinstance(self.value, str) or self.value.strip() == "":
            raise ValueError("TaskIntent must be a non-empty string")

    def __str__(self) -> str:
        return self.value

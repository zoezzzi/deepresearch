from dataclasses import dataclass


@dataclass(frozen=True)
class ReportUrl:
    value: str

    def __post_init__(self):
        if not isinstance(self.value, str) or not self.value or self.value.strip() == "":
            raise ValueError("ReportUrl must be a non-empty, non-whitespace string")

    def __str__(self) -> str:
        return self.value

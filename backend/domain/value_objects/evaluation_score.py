from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationScore:
    value: float

    def __post_init__(self):
        if not isinstance(self.value, (int, float)):
            raise ValueError("EvaluationScore must be a number")
        if self.value < 0.0 or self.value > 1.0:
            raise ValueError("EvaluationScore must be between 0.0 and 1.0")

    def __str__(self) -> str:
        return f"{self.value:.4f}"

    def __float__(self) -> float:
        return self.value

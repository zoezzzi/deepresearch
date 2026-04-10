from dataclasses import dataclass


@dataclass(frozen=True)
class Notices:
    value: str

    def __post_init__(self):
        if not isinstance(self.value, str):
            raise ValueError("Notices must be a string")

    def __str__(self) -> str:
        return self.value

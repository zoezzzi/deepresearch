from dataclasses import dataclass


@dataclass(frozen=True)
class SearchQuery:
    value: str

    def __post_init__(self):
        if not self.value or not isinstance(self.value, str) or self.value.strip() == "":
            raise ValueError("SearchQuery must be a non-empty string")

    def __str__(self) -> str:
        return self.value

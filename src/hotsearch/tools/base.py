from abc import ABC, abstractmethod
from typing import ClassVar, TypedDict


class StandardItem(TypedDict, total=False):
    """Every adapter item must normalize to this schema.
    Missing fields should be set to None or [].
    """

    id: str | None
    title: str
    url: str | None
    time: str | None
    tags: list[str]
    summary: str | None
    source_name: str | None
    timestamp: float
    raw: dict


class StandardResult(TypedDict):
    """Standardized output of every adapter.fetch() after normalize()."""

    source_name: str
    items: list[StandardItem]
    meta: dict | None
    output: str | None


REQUIRED_ITEM_FIELDS = ("title", "summary", "timestamp", "tags", "source_name")


def validate_standard_result(result: StandardResult) -> None:
    """Raise ValueError if any item is missing a required field."""
    for i, item in enumerate(result.get("items", [])):
        missing = [f for f in REQUIRED_ITEM_FIELDS if f not in item]
        if missing:
            raise ValueError(
                f"Item {i} missing required fields: {missing}"
            )


class ToolAdapter(ABC):
    """Abstract base for all data source adapters."""

    name: str
    category: str  # "trends" or "feeds"
    tags: ClassVar[list[str]] = []

    @abstractmethod
    def fetch(self, query: str = "", **kwargs) -> dict | list:
        """Fetch raw data from the source. Must return dict or list."""
        pass

    @abstractmethod
    def normalize(self, raw: dict | list) -> StandardResult:
        """Convert raw fetch() output to standardized format.
        MUST be implemented by every concrete adapter.
        Missing fields should be set to None / [] as appropriate.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__}.normalize() not implemented"
        )

    def is_available(self) -> bool:
        """Return False to skip registration (e.g. missing env vars)."""
        return True

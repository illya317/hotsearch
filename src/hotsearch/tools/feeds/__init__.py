import importlib
import pkgutil

from hotsearch.tools.base import StandardItem, StandardResult, ToolAdapter  # noqa: F401


class FeedAdapter(ToolAdapter):
    """Base class for all feed source adapters."""

    category = "feeds"
    display_name: str = ""
    state_file: str | None = None  # relative to CACHE_FEEDS_DIR

    def check_new(self) -> list[dict]:
        """Check for new items and return structured notifications.
        Each dict MUST contain:
          - title: str
          - summary: str
          - timestamp: float (unix timestamp)
        Additional fields (e.g. name, status) are optional.
        Override in subclass if the source supports new-item detection.
        """
        return []

    def get_status(self) -> list[dict]:
        """Return status entries for push status display.
        Each dict MUST contain:
          - title: str
          - summary: str
          - timestamp: float (unix timestamp)
        Additional fields (e.g. name, status) are optional.
        Override in subclass.
        """
        return []

    def get_daily_items(self, threshold: float) -> list[dict]:
        """Return recent items for daily summary.
        Each dict MUST contain:
          - title: str
          - summary: str
          - timestamp: float (unix timestamp)
        Additional fields (e.g. name, time) are optional.
        Override in subclass.
        """
        return []


_TOOLS: dict[str, FeedAdapter] = {}
_DISCOVERED = False


def _discover():
    global _TOOLS, _DISCOVERED
    if _DISCOVERED:
        return
    _DISCOVERED = True
    for _, name, _ in pkgutil.iter_modules(__path__):
        if name.startswith("_") or name == "base":
            continue
        try:
            module = importlib.import_module(f"{__name__}.{name}")
        except Exception:
            continue
        for obj_name in dir(module):
            obj = getattr(module, obj_name)
            if (
                isinstance(obj, type)
                and issubclass(obj, FeedAdapter)
                and obj is not FeedAdapter
            ):
                try:
                    instance = obj()
                    if instance.is_available():
                        _TOOLS[instance.name] = instance
                except Exception:
                    pass


def get_tools() -> list[FeedAdapter]:
    _discover()
    return list(_TOOLS.values())


def get_tool(name: str) -> FeedAdapter | None:
    _discover()
    return _TOOLS.get(name)

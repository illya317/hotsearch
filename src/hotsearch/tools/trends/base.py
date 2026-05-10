from hotsearch.tools.base import StandardItem, StandardResult, ToolAdapter  # noqa: F401


class TrendAdapter(ToolAdapter):
    """Base class for all trend source adapters."""

    category = "trends"

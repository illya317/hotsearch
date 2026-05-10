from hotsearch.tools.base import StandardItem, StandardResult, ToolAdapter  # noqa: F401


class FeedAdapter(ToolAdapter):
    """Base class for all feed source adapters."""

    category = "feeds"

    def check_new(self) -> list[str]:
        """Check for new items and return formatted notifications.
        Override in subclass if the source supports new-item detection.
        """
        return []

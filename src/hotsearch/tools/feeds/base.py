from hotsearch.tools.base import StandardItem, StandardResult, ToolAdapter  # noqa: F401


class FeedAdapter(ToolAdapter):
    """Base class for all feed source adapters."""

    category = "feeds"
    display_name: str = ""
    state_file: str | None = None  # relative to CACHE_FEEDS_DIR

    def check_new(self) -> list[str]:
        """Check for new items and return formatted notifications.
        Override in subclass if the source supports new-item detection.
        """
        return []

    def get_status(self) -> list[dict]:
        """Return status entries for push status display.
        Each entry: {'name': str, 'title': str, 'status': '✅已最新' | '🆕有更新' | '❌'}.
        Override in subclass.
        """
        return []

    def get_daily_items(self, threshold: float) -> list[dict]:
        """Return recent items for daily summary.
        Each item: {'name': str, 'title': str, 'time': str, 'timestamp': float}.
        Override in subclass.
        """
        return []

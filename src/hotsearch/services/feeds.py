#!/usr/bin/env python3
"""Check new videos/releases/laws and push notifications via Feishu."""

from concurrent.futures import ThreadPoolExecutor, as_completed

from hotsearch.tools.feeds import get_tools
from hotsearch.tools.system.feishu_send import send_to_feishu


class FeedsService:
    """Business layer: aggregate feeds from adapters, output standard JSON."""

    def collect(self, sources: list[str] | None = None, **kwargs) -> dict:
        tools = get_tools()
        if sources:
            tools = [t for t in tools if t.name in sources]

        results = []
        with ThreadPoolExecutor() as pool:
            futures = {pool.submit(t.fetch, **kwargs): t for t in tools}
            for future in as_completed(futures):
                tool = futures[future]
                try:
                    data = future.result()
                    normalized = tool.normalize(data)
                    results.append(
                        {"source": tool.name, "status": "ok", "data": normalized}
                    )
                except Exception as e:
                    results.append(
                        {"source": tool.name, "status": "error", "error": str(e)}
                    )

        return {"category": "feeds", "count": len(tools), "results": results}

    def check_new(self) -> list[str]:
        """Check all feed sources for new items and return formatted notifications."""
        notifications = []
        for tool in get_tools():
            try:
                items = tool.check_new()
                notifications.extend(items)
            except Exception:
                pass
        return notifications


def main():
    service = FeedsService()
    notifications = service.check_new()
    if notifications:
        msg = "🔔 新内容更新!\n\n" + "\n\n".join(notifications)
        print(msg)
        send_to_feishu(msg)
    else:
        print("No new content")


if __name__ == "__main__":
    main()

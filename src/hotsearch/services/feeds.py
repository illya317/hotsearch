#!/usr/bin/env python3
"""Feeds raw data collection: fetch all sources → normalize → save StandardResult."""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from hotsearch import CACHE_FEEDS_DIR
from hotsearch.tools.feeds import get_tools


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

    @staticmethod
    def load_latest() -> dict | None:
        """Load the latest feeds StandardResult from cache."""
        candidates = []
        for path in CACHE_FEEDS_DIR.glob("feeds_*.json"):
            try:
                ts = float(path.stem.split("_", 1)[1])
                candidates.append((ts, path))
            except Exception:
                continue
        if not candidates:
            return None
        latest = sorted(candidates, reverse=True)[0][1]
        return json.loads(latest.read_text(encoding="utf-8"))


def _save(result: dict) -> Path:
    CACHE_FEEDS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    ts = now.strftime("%Y%m%d_%H%M")
    path = CACHE_FEEDS_DIR / f"feeds_{ts}.json"
    payload = {
        **result,
        "time": now.strftime("%Y-%m-%d %H:%M"),
        "timestamp": time.time(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main():
    ap = argparse.ArgumentParser(description="Feeds raw data collection")
    ap.parse_args()

    service = FeedsService()
    result = service.collect()
    path = _save(result)
    print(path)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Trends data collection: fetch → normalize → save raw StandardResult.
No tagging, no sending. Pure data collection only.
"""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from hotsearch import CACHE_TRENDS_DIR, SCHEDULER_CONFIG
from hotsearch.tools.trends import get_tool, get_tools

# Load display names from trends.json
_PLATFORM_CFG = json.loads(SCHEDULER_CONFIG.read_text())
PLATFORM_NAMES = {k: v["display_name"] for k, v in _PLATFORM_CFG["tasks"].items()}


class TrendsService:
    """Business layer: aggregate trends from adapters, output standard JSON."""

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
                        {
                            "source": tool.name,
                            "status": "ok",
                            "data": normalized,
                            "tags": tool.tags,
                        }
                    )
                except Exception as e:
                    results.append(
                        {
                            "source": tool.name,
                            "status": "error",
                            "error": str(e),
                            "tags": tool.tags,
                        }
                    )

        return {"category": "trends", "count": len(tools), "results": results}

    @staticmethod
    def load_latest(mode: str) -> dict | None:
        """Load the latest saved StandardResult for a given mode from cache."""
        candidates = []
        for path in CACHE_TRENDS_DIR.glob(f"{mode}_*.json"):
            try:
                ts = float(path.stem.split("_", 1)[1])
                candidates.append((ts, path))
            except Exception:
                continue
        if not candidates:
            return None
        latest = sorted(candidates, reverse=True)[0][1]
        return json.loads(latest.read_text(encoding="utf-8"))


def _resolve_mode(mode: str) -> tuple[str, dict]:
    """Map task name to (adapter_name, fetch_kwargs)."""
    if mode in ("zhihu", "weibo", "eastmoney", "ithome"):
        return "hotsearch", {"platform": mode, "limit": 5}
    if mode == "ainews":
        return "ainews", {"source": "decoder", "limit": 5}
    if mode == "github":
        return "github", {"limit": 5}
    raise ValueError(f"Unknown mode: {mode}")


def _save(result: dict, mode: str) -> Path:
    CACHE_TRENDS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    ts = now.strftime("%Y%m%d_%H%M")
    path = CACHE_TRENDS_DIR / f"{mode}_{ts}.json"
    payload = {
        **result,
        "mode": mode,
        "name": PLATFORM_NAMES.get(mode, mode),
        "time": now.strftime("%Y-%m-%d %H:%M"),
        "timestamp": time.time(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main():
    ap = argparse.ArgumentParser(description="Trends raw data collection")
    ap.add_argument(
        "mode", help="Task name (zhihu, weibo, eastmoney, ithome, ainews, github)"
    )
    args = ap.parse_args()

    if args.mode not in PLATFORM_NAMES:
        print(f"Unknown mode: {args.mode}")
        print(f"Available: {', '.join(PLATFORM_NAMES.keys())}")
        return

    adapter_name, fetch_kwargs = _resolve_mode(args.mode)
    adapter = get_tool(adapter_name)
    if not adapter:
        raise RuntimeError(f"Adapter {adapter_name} not found")

    raw = adapter.fetch(**fetch_kwargs)
    normalized = adapter.normalize(raw)

    result = {
        "category": "trends",
        "count": 1,
        "results": [
            {
                "source": adapter.name,
                "status": "ok",
                "data": normalized,
                "tags": adapter.tags,
            }
        ],
    }

    path = _save(result, args.mode)
    print(path)


if __name__ == "__main__":
    main()

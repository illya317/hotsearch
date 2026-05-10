#!/usr/bin/env python3
"""
Scheduled trends delivery via Feishu.
Task definitions in config/trends.json, schedules in config/cron.json.
"""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from hotsearch import CACHE_TRENDS_DIR, SCHEDULER_CONFIG
from hotsearch.tools.system.feishu_send import send_to_feishu
from hotsearch.tools.trends import get_tools

# Load scheduler config
_scheduler_cfg = json.loads(SCHEDULER_CONFIG.read_text())
_tasks = _scheduler_cfg["tasks"]

PLATFORM_NAMES = {k: v["display_name"] for k, v in _tasks.items()}


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


def _last_content(mode: str) -> str | None:
    files = sorted(CACHE_TRENDS_DIR.glob(f"{mode}_*.json"), reverse=True)
    if not files:
        return None
    try:
        data = json.loads(files[0].read_text(encoding="utf-8"))
        return data.get("content")
    except Exception:
        return None


def _save(mode: str, name: str, content: str):
    CACHE_TRENDS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    ts = now.strftime("%Y%m%d_%H%M")
    path = CACHE_TRENDS_DIR / f"{mode}_{ts}.json"
    path.write_text(
        json.dumps(
            {
                "mode": mode,
                "name": name,
                "content": content,
                "time": now.strftime("%Y-%m-%d %H:%M"),
                "timestamp": time.time(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def _fetch_for_mode(mode: str) -> str:
    """Fetch content for a specific scheduled mode (legacy CLI mapping)."""
    if mode in ("zhihu", "weibo", "eastmoney", "ithome"):
        adapter = next((t for t in get_tools() if t.name == "hotsearch"), None)
        if not adapter:
            raise RuntimeError("hotsearch adapter not found")
        data = adapter.fetch(platform=mode, limit=5)
        return json.dumps(data, ensure_ascii=False)
    elif mode == "ainews":
        adapter = next((t for t in get_tools() if t.name == "ainews"), None)
        if not adapter:
            raise RuntimeError("ainews adapter not found")
        data = adapter.fetch(source="decoder", limit=5)
        return json.dumps(data, ensure_ascii=False)
    elif mode == "github":
        adapter = next((t for t in get_tools() if t.name == "github"), None)
        if not adapter:
            raise RuntimeError("github adapter not found")
        data = adapter.fetch(limit=5)
        return json.dumps(data, ensure_ascii=False)
    else:
        raise ValueError(f"Unknown mode: {mode}")


def task_scheduled(name, content):
    msg = f"⏰ {name}\n\n{content}"
    if len(msg) > 4000:
        msg = msg[:3950] + "\n\n... (截断)"
    print(msg)
    send_to_feishu(msg)


def main():
    ap = argparse.ArgumentParser(description="Scheduled trends delivery")
    ap.add_argument("mode", help="Task name from trends.json")
    ap.add_argument(
        "--no-send", action="store_true", help="Save to cache but do not send Feishu"
    )
    args = ap.parse_args()

    now = datetime.now()
    mode = args.mode

    print(f"[{now.strftime('%Y-%m-%d %H:%M')}] Mode: {mode}")

    if mode not in PLATFORM_NAMES:
        print(f"Unknown mode: {mode}")
        print(f"Available: {', '.join(PLATFORM_NAMES.keys())}")
        return

    content = _fetch_for_mode(mode)
    last = _last_content(mode)
    if last == content:
        print("Content unchanged, skip save and send")
        return

    path = _save(mode, PLATFORM_NAMES[mode], content)
    print(f"Saved to {path}")

    if not args.no_send:
        task_scheduled(PLATFORM_NAMES[mode], content)
    else:
        print("Skipped Feishu send (--no-send)")


if __name__ == "__main__":
    main()

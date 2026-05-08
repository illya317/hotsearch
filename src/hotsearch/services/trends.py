#!/usr/bin/env python3
"""
Scheduled trends delivery via Feishu.
Task definitions in config/trends.json, schedules in config/cron.json.
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime

from hotsearch import CACHE_TRENDS_DIR, SCHEDULER_CONFIG
from hotsearch.tools.system.feishu_send import send_to_feishu


def _run_tool(*args) -> str:
    r = subprocess.run(args, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise Exception(r.stderr.strip() or "tool failed")
    return r.stdout.strip()


def _last_content(mode: str) -> str | None:
    """Read the most recent saved content for this mode."""
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


# Load scheduler config
_scheduler_cfg = json.loads(SCHEDULER_CONFIG.read_text())
_tasks = _scheduler_cfg["tasks"]

COMMANDS = {k: v["command"] for k, v in _tasks.items() if "command" in v}
PLATFORM_NAMES = {k: v["display_name"] for k, v in _tasks.items()}


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

    if mode not in COMMANDS:
        print(f"Unknown mode: {mode}")
        print(f"Available: {', '.join(COMMANDS.keys())}")
        return

    content = _run_tool(*COMMANDS[mode])
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

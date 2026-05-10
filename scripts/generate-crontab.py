#!/usr/bin/env python3
"""Generate crontab entries from config/cron.json and optionally install them.

Usage:
    python3 scripts/generate-crontab.py          # print to stdout
    python3 scripts/generate-crontab.py --install # install via crontab command
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CRON_JSON = PROJECT_ROOT / "config" / "cron.json"

# Project root on the server (used in crontab commands)
SERVER_ROOT = "/root/.openclaw/workspace/hotsearch"


def generate() -> str:
    cfg = json.loads(CRON_JSON.read_text(encoding="utf-8"))
    lines: list[str] = []

    # System-level tasks (not managed by cron-task.sh)
    lines.append("# System tasks (not managed by cron-task.sh)")
    lines.append(
        "*/5 * * * * flock -xn /tmp/stargate.lock -c "
        "'/usr/local/qcloud/stargate/admin/start.sh > /dev/null 2>&1 &'"
    )
    lines.append("")

    # Feeds
    feeds = cfg.get("tasks", {}).get("feeds", {})
    if feeds:
        lines.append("# Feeds check")
        schedule = feeds.get("schedule", "7 * * * *")
        lines.append(f"{schedule} {SERVER_ROOT}/scripts/cron-task.sh feeds")
        lines.append("")

    # Trends
    trends = cfg.get("trends", {})
    if trends:
        lines.append("# Trends delivery")
        for name, task_cfg in trends.items():
            for schedule in task_cfg.get("schedules", []):
                lines.append(f"{schedule} {SERVER_ROOT}/scripts/cron-task.sh {name}")
        lines.append("")

    # Status
    status = cfg.get("tasks", {}).get("status", {})
    if status:
        lines.append("# Server status check")
        schedule = status.get("schedule", "57 8,20 * * *")
        lines.append(f"{schedule} {SERVER_ROOT}/scripts/cron-task.sh status")
        lines.append("")

    # Service keep-alive (not managed by cron-task.sh)
    lines.append("# Ensure routers/api.py is running")
    lines.append(
        "* * * * * pgrep -f 'python3 -m routers.api' > /dev/null || "
        f"(cd {SERVER_ROOT}/src/hotsearch && "
        f"PYTHONPATH={SERVER_ROOT}/src nohup python3 -m routers.api > /dev/null 2>&1 &)"
    )

    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Generate crontab from cron.json")
    ap.add_argument(
        "--install",
        action="store_true",
        help="Install generated crontab via crontab command",
    )
    args = ap.parse_args()

    output = generate()

    if args.install:
        try:
            subprocess.run(["crontab", "-"], input=output, text=True, check=True)
            print("Crontab installed successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to install crontab: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(output, end="")


if __name__ == "__main__":
    main()

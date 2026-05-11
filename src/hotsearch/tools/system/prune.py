#!/usr/bin/env python3
"""
Prune expired cache data.

Targets:
- feeds:   Remove expired entries from video/release state files
- trends:  Delete trend cache files older than N days
- search:  Delete search cache files older than N days

Usage:
    python3 -m hotsearch.tools.system.prune
    python3 -m hotsearch.tools.system.prune --days 3 --dry-run
    python3 -m hotsearch.tools.system.prune --targets trends,search
"""

import argparse
import json
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
import sys  # noqa: E402

sys.path.insert(0, str(_PROJECT_ROOT / "src"))
from hotsearch import CACHE_FEEDS_DIR, CACHE_SEARCH_DIR, CACHE_TRENDS_DIR  # noqa: E402


def _is_expired(ts: float, days: int) -> bool:
    return time.time() - ts > days * 86400


def prune_trends(days: int, dry_run: bool):
    """Delete trend cache files older than N days (by mtime)."""
    count = 0
    for path in CACHE_TRENDS_DIR.glob("*.json"):
        try:
            if _is_expired(path.stat().st_mtime, days):
                if not dry_run:
                    path.unlink()
                count += 1
        except Exception:
            continue
    action = "Would delete" if dry_run else "Deleted"
    print(f"{action} {count} trend cache files (>{days}d)")


def prune_search(days: int, dry_run: bool):
    """Delete search cache files older than N days (by mtime)."""
    count = 0
    for path in CACHE_SEARCH_DIR.glob("*.json"):
        try:
            if _is_expired(path.stat().st_mtime, days):
                if not dry_run:
                    path.unlink()
                count += 1
        except Exception:
            continue
    action = "Would delete" if dry_run else "Deleted"
    print(f"{action} {count} search cache files (>{days}d)")


def _prune_state_file(path: Path, key: str, days: int, dry_run: bool) -> int:
    """Remove expired entries from a state file. Returns count removed."""
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data.get(key, {})
        if not isinstance(items, dict):
            return 0
        expired = [
            k
            for k, v in items.items()
            if isinstance(v, dict) and _is_expired(v.get("timestamp", 0), days)
        ]
        if expired:
            if not dry_run:
                for k in expired:
                    del items[k]
                path.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            return len(expired)
    except Exception as e:
        print(f"State file error ({path.name}): {e}")
    return 0


def prune_feeds(days: int, dry_run: bool):
    """Remove expired entries from feed state files."""
    total = 0

    vc = _prune_state_file(
        CACHE_FEEDS_DIR / "video_state.json", "videos", days, dry_run
    )
    if vc:
        print(
            f"{'Would remove' if dry_run else 'Removed'} {vc} video entries (>{days}d)"
        )
        total += vc

    rc = _prune_state_file(
        CACHE_FEEDS_DIR / "release_state.json", "releases", days, dry_run
    )
    if rc:
        print(
            f"{'Would remove' if dry_run else 'Removed'} {rc} release entries (>{days}d)"
        )
        total += rc

    action = "Would remove" if dry_run else "Removed"
    print(f"{action} {total} total feed entries (>{days}d)")


def prune_trends_state(days: int, dry_run: bool):
    """Remove expired entries from trends state file."""
    from hotsearch.tools.trends.state import prune_state

    if dry_run:
        # prune_state doesn't support dry-run; load and count
        from hotsearch.tools.trends.state import load_state, _is_expired

        state = load_state()
        count = 0
        for platform, items in state.items():
            for title, meta in items.items():
                if isinstance(meta, dict) and _is_expired(meta.get("timestamp", 0), days):
                    count += 1
        print(f"Would remove {count} trend state entries (>{days}d)")
    else:
        count = prune_state(days)
        if count:
            print(f"Removed {count} trend state entries (>{days}d)")
        else:
            print(f"No expired trend state entries (>{days}d)")


TARGETS = {
    "trends": prune_trends,
    "trends_state": prune_trends_state,
    "search": prune_search,
    "feeds": prune_feeds,
}


def main():
    ap = argparse.ArgumentParser(description="Prune expired cache data")
    ap.add_argument(
        "--days", type=int, default=7, help="Expiration threshold in days (default: 7)"
    )
    ap.add_argument(
        "--targets",
        default="feeds,trends,search",
        help="Comma-separated targets: feeds,trends,search",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be deleted without deleting",
    )
    args = ap.parse_args()

    targets = [t.strip() for t in args.targets.split(",")]
    for t in targets:
        if t in TARGETS:
            TARGETS[t](args.days, args.dry_run)
        else:
            print(f"Unknown target: {t}")


if __name__ == "__main__":
    main()

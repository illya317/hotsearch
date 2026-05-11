"""Trends state management — persistent dedup by title per platform.

State file: data/cache/trends/trends_state.json
Structure: {platform: {title: {timestamp, rank, heat_str}}}
"""

import json
import time
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
STATE_FILE = _PROJECT_ROOT / "data" / "cache" / "trends" / "trends_state.json"


def _is_expired(ts: float, days: int) -> bool:
    return time.time() - ts > days * 86400


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def get_new_items(platform: str, items: list[dict]) -> list[dict]:
    """Return items not seen before for this platform, and update state."""
    state = load_state()
    platform_state = state.setdefault(platform, {})
    new_items = []
    now = time.time()

    for item in items:
        title = item.get("title", "")
        if not title or title in platform_state:
            continue
        new_items.append(item)
        platform_state[title] = {
            "timestamp": now,
            "rank": item.get("rank"),
            "heat_str": item.get("heat_str"),
        }

    save_state(state)
    return new_items


def prune_state(days: int) -> int:
    """Remove entries older than N days. Returns count removed."""
    state = load_state()
    total = 0
    for platform, items in list(state.items()):
        expired = [
            title
            for title, meta in items.items()
            if isinstance(meta, dict) and _is_expired(meta.get("timestamp", 0), days)
        ]
        for title in expired:
            del items[title]
            total += 1
        if not items:
            del state[platform]
    if total:
        save_state(state)
    return total

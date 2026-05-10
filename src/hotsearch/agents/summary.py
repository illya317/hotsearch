#!/usr/bin/env python3
"""
Summary agent: search enrichment + template rendering + Feishu delivery.

Usage:
    python3 -m hotsearch.agents.summary --source zhihu --send
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import jinja2

from hotsearch import CACHE_TRENDS_DIR
from hotsearch.services.scoring import ScoringService
from hotsearch.services.search import SearchService
from hotsearch.tools.logger import get_logger
from hotsearch.tools.system.feishu_send import send_to_feishu

_log = get_logger(__name__)
_CACHE_CRON_DIR = Path(CACHE_TRENDS_DIR).parent / "cron"


class SummaryAgent:
    """Enrich high-score items via search, render summary template, send to Feishu."""

    def __init__(self):
        self.searcher = SearchService()
        self.scorer = ScoringService()
        self._jinja = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                str(
                    Path(__file__).resolve().parent.parent.parent.parent
                    / "config"
                    / "prompts"
                )
            )
        )

    def run(self, source: str, send: bool = False) -> str:
        """Load scored data, enrich, render, optionally send. Returns formatted text."""
        scored = self._load_scored(source)
        if scored is None:
            _log.error("no scored data for %s", source)
            sys.exit(1)

        mode = scored.get("mode", source)
        name = scored.get("name", mode)
        total = scored.get("total", 0)

        deep = scored.get("deep", [])
        regular = scored.get("regular", [])
        discard = scored.get("discard", [])

        # Enrich deep items with search context
        for item in deep:
            try:
                self.searcher.enrich_item(item)
            except Exception as e:
                _log.warning("enrich failed for '%s': %s", item.get("title", ""), e)

        # Render
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        text = self._jinja.get_template("summary.j2").render(
            name=name,
            time=now,
            deep_items=deep,
            regular_items=regular,
            total=total,
            sent=len(deep) + len(regular),
            discarded=len(discard),
        )

        # Truncate for Feishu (4000 char limit)
        if len(text) > 4000:
            text = text[:3950] + "\n\n... (截断)"

        # Save final output
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        out_path = _CACHE_CRON_DIR / f"{mode}_final_{ts}.md"
        out_path.write_text(text, encoding="utf-8")

        _log.info(
            "%s: %d deep, %d regular, %d discarded, sent=%s",
            mode,
            len(deep),
            len(regular),
            len(discard),
            send,
        )

        if send:
            print(text)
            send_to_feishu(text)

        return text

    def _load_scored(self, source: str) -> dict | None:
        """Find the latest scored JSON for a mode."""
        candidates = []
        for path in _CACHE_CRON_DIR.glob(f"{source}_scored_*.json"):
            try:
                candidates.append((path.stat().st_mtime, path))
            except Exception:
                continue
        if not candidates:
            return None
        latest = sorted(candidates, reverse=True)[0][1]
        return json.loads(latest.read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser(description="Summary agent: enrich + render + send")
    ap.add_argument("--source", required=True, help="Mode name or 'feeds'")
    ap.add_argument(
        "--send", action="store_true", help="Send to Feishu after rendering"
    )
    args = ap.parse_args()

    agent = SummaryAgent()
    agent.run(args.source, send=args.send)


if __name__ == "__main__":
    main()

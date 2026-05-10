#!/usr/bin/env python3
"""
Summary agent: search enrichment + template rendering + Feishu delivery.
Supports single source or --source all for combined briefing.

Usage:
    python3 -m hotsearch.agents.summary --source zhihu --send
    python3 -m hotsearch.agents.summary --source all --send
"""

import argparse
import json
import sys
from datetime import datetime

import jinja2

from hotsearch import CACHE_CRON_DIR, CACHE_SUMMARY_DIR, CONFIG_DIR, OUTPUT_DIR, PROJECT_ROOT, RANKING_DIR
from hotsearch.llms import llm_for_agent
from hotsearch.services.search import SearchService
from hotsearch.tools.logger import get_logger
from hotsearch.tools.system.feishu_send import send_to_feishu

_log = get_logger("summary")


def _load_scoring_rules() -> dict:
    import json as _json
    path = CONFIG_DIR / "scoring_rules.json"
    if path.exists():
        return _json.loads(path.read_text(encoding="utf-8"))
    return {}


def _detail_threshold() -> int:
    return _load_scoring_rules().get("detail_threshold", 70)


class SummaryAgent:
    """Enrich high-score items via search, render summary template, send to Feishu."""

    def __init__(self):
        self.searcher = SearchService()
        self.llm = llm_for_agent("tag")
        self._jinja = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(PROJECT_ROOT / "config" / "prompts"))
        )
        self._scoring_rules = _load_scoring_rules()

    def run(self, source: str, send: bool = False) -> str:
        if source == "all":
            return self._run_all(send)
        return self._run_single(source, send)

    def _run_single(self, source: str, send: bool) -> str:
        scored = self._load_scored(source)
        if scored is None:
            _log.error("no scored data for %s", source)
            sys.exit(1)
        return self._render_and_send(source, [scored], send)

    def _run_all(self, send: bool) -> str:
        """Load all scored data, combine, render one briefing."""
        all_scored = []
        paths = sorted(
            CACHE_CRON_DIR.glob("*_scored_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for path in paths:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                # Only take the latest per source
                mode = data.get("mode", "")
                if mode and not any(s.get("mode") == mode for s in all_scored):
                    all_scored.append(data)
            except Exception:
                continue

        if not all_scored:
            _log.error("no scored data found")
            sys.exit(1)

        # Sort by source name for consistent ordering
        all_scored.sort(key=lambda s: s.get("mode", ""))

        return self._render_and_send("all", all_scored, send)

    def _summarize_result(self, title: str, raw_context: str) -> str:
        """Use LLM to condense search results into a concise Chinese summary."""
        if not raw_context or not raw_context.strip():
            return ""

        prompt = self._jinja.get_template("search_summarize.j2").render(
            title=title, raw_context=raw_context
        )
        try:
            raw = self.llm.chat(
                [{"role": "user", "content": prompt}]
            )
            text = raw.strip().strip('"').strip("'")
            # Strip markdown formatting
            for md in ["**", "*", "#", "`"]:
                text = text.replace(md, "")
            text = text.strip()
            if not text or text == "暂无可靠信息":
                return ""
            if len(text) > 300:
                text = text[:297] + "..."
            return text
        except Exception:
            return ""

    def _render_and_send(self, source: str, scored_list: list[dict], send: bool) -> str:
        """Combine scored data, enrich high-score items, render, save, send."""
        now = datetime.now()
        ts = now.strftime("%Y%m%d_%H%M")
        time_str = now.strftime("%Y-%m-%d %H:%M")
        hour = now.hour
        period = "早" if 5 <= hour < 12 else ("晚" if 17 <= hour < 23 else "快")

        # Combine all items with source label
        all_items = []
        stats = []
        for scored in scored_list:
            mode = scored.get("mode", "")
            name = scored.get("name", mode)
            deep = scored.get("deep", [])
            brief = scored.get("brief", [])
            combined = deep + brief
            for item in combined:
                item["source"] = name
            all_items.extend(combined)
            scores = [i.get("score", 0) for i in combined]
            stats.append({
                "source": name,
                "count": len(combined),
                "avg": sum(scores) // len(scores) if scores else 0,
            })

        # Global top-N curation: sort all items by score
        all_items.sort(key=lambda i: i.get("score", 0), reverse=True)
        top_deep = self._scoring_rules.get("top_deep_count", 5)
        top_brief = self._scoring_rules.get("top_brief_count", 10)
        top_total = top_deep + top_brief

        # Enrich high-score candidates among top N
        for item in all_items[:top_total]:
            if item.get("score", 0) >= _detail_threshold():
                try:
                    self.searcher.enrich_item(item)
                    raw = item.get("search_context", "")
                    if raw:
                        item["search_context"] = self._summarize_result(item["title"], raw)
                except Exception as e:
                    _log.warning("enrich failed '%s': %s", item.get("title", ""), e)

        deep_items = all_items[:top_deep]
        brief_items = all_items[top_deep:top_total]

        total = len(deep_items) + len(brief_items)
        discarded = max(0, sum(
            len(s.get("deep", [])) + len(s.get("brief", [])) + len(s.get("discard", []))
            for s in scored_list
        ) - total)

        text = self._jinja.get_template("summary.j2").render(
            period=period,
            time=time_str,
            deep_items=deep_items,
            brief_items=brief_items,
            total=total,
            sent=total,
            discarded=discarded,
            stats=stats,
        )

        # Truncate for Feishu
        if len(text) > 4000:
            text = text[:3950] + "\n\n... (截断)"

        # Save to cache/summary/ (structured JSON for later query)
        CACHE_SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
        summary_json = {
            "period": period,
            "time": time_str,
            "timestamp": now.timestamp(),
            "deep": deep_items,
            "brief": brief_items,
            "stats": stats,
            "total": total,
            "discarded": discarded,
        }
        json_path = CACHE_SUMMARY_DIR / f"summary_{ts}.json"
        json_path.write_text(json.dumps(summary_json, ensure_ascii=False, indent=2), encoding="utf-8")

        # Save formatted output
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        md_path = OUTPUT_DIR / f"summary_{ts}.md"
        md_path.write_text(text, encoding="utf-8")

        # Save 3 ranking files
        RANKING_DIR.mkdir(parents=True, exist_ok=True)

        def _save_ranking(suffix, sort_key):
            ranked = sorted(all_items, key=sort_key, reverse=True)
            items = [{
                "rank": i + 1,
                "title": it.get("title", ""),
                "sim_score": it.get("sim_score", 0),
                "combined_score": it.get("combined_score", 0),
                "final_score": it.get("score", 0),
                "tags": it.get("tags", []),
                "source": it.get("source", ""),
            } for i, it in enumerate(ranked)]
            path = RANKING_DIR / f"ranking_{ts}_{suffix}.json"
            path.write_text(json.dumps({
                "time": time_str, "period": period, "total": len(items),
                "items": items,
            }, ensure_ascii=False, indent=2), encoding="utf-8")

        _save_ranking("raw", lambda i: i.get("sim_score", 0))
        _save_ranking("weighted", lambda i: i.get("combined_score", 0))
        _save_ranking("agent", lambda i: i.get("score", 0))

        _log.info("all: %d deep, %d brief, %d sources, sent=%s",
                   len(deep_items), len(brief_items), len(scored_list), send)

        if send:
            print(text)
            send_to_feishu(text)

        return text

    def _load_scored(self, source: str) -> dict | None:
        candidates = []
        for path in CACHE_CRON_DIR.glob(f"{source}_scored_*.json"):
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
    ap.add_argument("--source", required=True, help="Mode name, 'feeds', or 'all'")
    ap.add_argument("--send", action="store_true", help="Send to Feishu after rendering")
    args = ap.parse_args()

    agent = SummaryAgent()
    agent.run(args.source, send=args.send)


if __name__ == "__main__":
    main()

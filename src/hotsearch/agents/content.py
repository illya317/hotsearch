#!/usr/bin/env python3
"""
Content agent: classify + score pipeline for cron data.

Usage:
    python3 -m hotsearch.agents.content --source zhihu
"""

import argparse
import json
import sys
import time
from datetime import datetime

import jinja2

from hotsearch import CACHE_CRON_DIR
from hotsearch.config import prompt_templates
from hotsearch.llms import LLMClient, llm_for_agent
from hotsearch.services.feeds import FeedsService
from hotsearch.services.scoring import ScoringService
from hotsearch.services.trends import TrendsService
from hotsearch.tools.logger import get_logger
from hotsearch.tools.tag import TAG_RULES, classify

_log = get_logger(__name__)

_templates = prompt_templates()
_jinja_env = jinja2.Environment(loader=jinja2.DictLoader(_templates))


class TagEngine:
    """Classify items using keyword matching + LLM fallback."""

    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm or llm_for_agent("tag")

    def classify_all(self, result: dict) -> dict:
        """In-place tag all items. Returns uncertain titles."""
        uncertain: list[str] = []
        for r in result.get("results", []):
            if r.get("status") != "ok":
                continue
            for item in r.get("data", {}).get("items", []):
                title = item.get("title", "")
                if not title:
                    continue
                tags = classify(title)
                if "uncertain" in tags:
                    tags = self._llm_classify(title)
                    if "uncertain" in tags:
                        uncertain.append(title)
                item["tags"] = tags
        result["uncertain_count"] = len(uncertain)
        return result

    def _llm_classify(self, title: str) -> list[str]:
        prompt = _jinja_env.get_template("tag_classify").render(
            tags=", ".join(TAG_RULES.keys()), title=title
        )
        messages = [
            {"role": "system", "content": "你是中文内容分类助手。只输出 JSON 数组。"},
            {"role": "user", "content": prompt},
        ]
        try:
            raw = self.llm.chat(messages, max_tokens=256)
            text = raw.strip().strip("`").replace("json", "").strip()
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict) and "tags" in parsed:
                return parsed["tags"]
            return ["uncertain"]
        except Exception:
            return ["uncertain"]

    def suggest_updates(self, uncertain_titles: list[str]) -> dict | None:
        """Ask LLM to suggest TAG_RULES keyword additions."""
        if not uncertain_titles:
            return None
        prompt = _jinja_env.get_template("tag").render(
            rules=json.dumps(TAG_RULES, ensure_ascii=False, indent=2),
            titles=uncertain_titles,
        )
        messages = [
            {"role": "system", "content": "你是中文内容分类助手。"},
            {"role": "user", "content": prompt},
        ]
        try:
            raw = self.llm.chat(messages, max_tokens=2048)
            text = raw.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            return json.loads(text.strip())
        except Exception as e:
            _log.error("suggest_updates failed: %s", e)
            return None


class ContentAgent:
    """Orchestrate tag classification + preference scoring for a data source."""

    def __init__(self):
        self.tag_engine = TagEngine()
        self.scorer = ScoringService()

    def run(self, source: str) -> dict:
        """Load raw data, classify, score, save. Returns scored data dict."""
        if source == "feeds":
            raw = FeedsService.load_latest()
        else:
            raw = TrendsService.load_latest(source)

        if raw is None:
            _log.error("no raw data for %s", source)
            sys.exit(1)

        mode = raw.get("mode", source)
        name = raw.get("name", mode)

        # Step 1: Classify
        self.tag_engine.classify_all(raw)

        # Step 2: Score
        all_items = []
        for r in raw.get("results", []):
            if r.get("status") != "ok":
                continue
            for item in r.get("data", {}).get("items", []):
                self.scorer.score(item)
                all_items.append(item)

        deep, regular, discard = self.scorer.classify_by_score(all_items)

        # Step 3: Save
        scored_data = {
            "mode": mode,
            "name": name,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "timestamp": time.time(),
            "total": len(all_items),
            "uncertain_count": raw.get("uncertain_count", 0),
            "deep": deep,
            "regular": regular,
            "discard": discard,
        }

        CACHE_CRON_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        out_path = CACHE_CRON_DIR / f"{mode}_scored_{ts}.json"
        out_path.write_text(
            json.dumps(scored_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        scores = [i.get("score", 0) for i in all_items]
        _log.info(
            "%s: %d tagged, %d uncertain, scored [%d-%d]",
            mode,
            len(all_items),
            raw.get("uncertain_count", 0),
            min(scores) if scores else 0,
            max(scores) if scores else 0,
        )

        print(out_path)
        return scored_data


def main():
    ap = argparse.ArgumentParser(description="Content agent: classify + score")
    ap.add_argument("--source", required=True, help="Mode name or 'feeds'")
    args = ap.parse_args()

    agent = ContentAgent()
    agent.run(args.source)


if __name__ == "__main__":
    main()

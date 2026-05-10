#!/usr/bin/env python3
"""Scoring service: compute weight scores for tagged items."""

import json
import re

from hotsearch import CONFIG_DIR
from hotsearch.config import prompt_templates


class ScoringService:
    """Pure algorithm: score items based on tags + keywords + source + rules."""

    def __init__(self):
        self.rules = self._load_scoring_rules()
        self.deep_dive_triggers = self._parse_deep_dive_triggers()

    def _load_scoring_rules(self) -> dict:
        path = CONFIG_DIR / "scoring_rules.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {
            "tag_base": {},
            "keyword_bonus": {},
            "keyword_penalty": {},
            "source_bonus": {},
            "llm_refine_threshold": 60,
            "detail_threshold": 80,
            "high_threshold": 70,
            "low_threshold": 30,
        }

    def _parse_deep_dive_triggers(self) -> set[str]:
        """Parse deep-dive triggers from config/prompts/preference.md."""
        text = prompt_templates().get("preference", "")
        triggers: set[str] = set()
        current_section = None
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("## "):
                title = stripped[3:].strip()
                if "深入搜索" in title or "deep" in title.lower():
                    current_section = "deep_dive"
                else:
                    current_section = None
                continue
            if current_section and stripped.startswith("- "):
                keyword = stripped[2:].strip()
                keyword = re.sub(r"（.*?）|\(.*?\)", "", keyword).strip()
                if keyword:
                    triggers.add(keyword)
        return triggers

    def score(self, item: dict) -> int:
        """Compute score for a single tagged item. Mutates item in-place."""
        tags = item.get("tags", [])
        title = item.get("title", "")
        score = 0

        # 1. Tag base scores (sum for multi-tag)
        tag_base = self.rules.get("tag_base", {})
        for tag in tags:
            score += tag_base.get(tag, 0)

        # 2. Keyword bonuses
        title_lower = title.lower()
        for keyword, bonus in self.rules.get("keyword_bonus", {}).items():
            if keyword.lower() in title_lower:
                score += bonus

        # 3. Keyword penalties
        for keyword, penalty in self.rules.get("keyword_penalty", {}).items():
            if keyword.lower() in title_lower:
                score += penalty

        # 4. Source bonus
        source_name = item.get("source_name", "")
        source = item.get("source", "")
        for src_key, bonus in self.rules.get("source_bonus", {}).items():
            if src_key in source_name or src_key in source:
                score += bonus

        # 5. Deep dive flag
        if self._match_deep_dive(title, tags):
            item["deep_dive"] = True

        # Clamp to [0, 100]
        score = max(0, min(100, score))
        item["score"] = score
        return score

    def _match_deep_dive(self, title: str, tags: list[str]) -> bool:
        for trigger in self.deep_dive_triggers:
            if trigger in title or any(trigger in tag for tag in tags):
                return True
        return False

    def classify_by_score(
        self, items: list[dict]
    ) -> tuple[list[dict], list[dict], list[dict]]:
        """Split items into deep (>=high), regular (low-high), discard (<low)."""
        high = self.rules.get("high_threshold", 70)
        low = self.rules.get("low_threshold", 30)
        deep = [i for i in items if i.get("score", 0) >= high]
        regular = [i for i in items if low <= i.get("score", 0) < high]
        discard = [i for i in items if i.get("score", 0) < low]
        return deep, regular, discard

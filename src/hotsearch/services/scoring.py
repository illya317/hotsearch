#!/usr/bin/env python3
"""Scoring service: compute weight scores for tagged items."""

import json
import re
from typing import Any

from hotsearch import CONFIG_DIR
from hotsearch.config import prompt_templates


class ScoringService:
    """Pure algorithm: score items based on tags + user preferences."""

    def __init__(self):
        self.params = self._load_params()
        self.rules = self._parse_preference()

    def _load_params(self) -> dict:
        path = CONFIG_DIR / "preference.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {
            "base_score": 50,
            "keep_bonus": 30,
            "interest_bonus": 20,
            "discard_penalty": 40,
            "high_threshold": 70,
            "low_threshold": 30,
        }

    def _parse_preference(self) -> dict[str, set[str]]:
        """Parse config/prompts/preference.md into structured rules."""
        text = prompt_templates().get("preference", "")
        rules: dict[str, set[str]] = {
            "auto_keep": set(),
            "auto_discard": set(),
            "interests": set(),
            "deep_dive_triggers": set(),
        }

        current_section = None
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("## "):
                title = stripped[3:].strip()
                if "自动保留" in title:
                    current_section = "auto_keep"
                elif "自动丢弃" in title:
                    current_section = "auto_discard"
                elif "兴趣" in title:
                    current_section = "interests"
                elif "深入搜索" in title or "deep" in title.lower():
                    current_section = "deep_dive_triggers"
                else:
                    current_section = None
                continue

            if current_section and stripped.startswith("- "):
                keyword = stripped[2:].strip()
                # Remove inline comments and extract meaningful text
                keyword = re.sub(r"（.*?）|\(.*?\)", "", keyword).strip()
                if keyword:
                    rules[current_section].add(keyword)

        return rules

    def score(self, item: dict) -> int:
        """Compute score for a single tagged item. Mutates item in-place."""
        tags = item.get("tags", [])
        title = item.get("title", "")
        score = self.params["base_score"]

        for tag in tags:
            if tag in self.rules["auto_keep"]:
                score += self.params["keep_bonus"]
            if tag in self.rules["auto_discard"]:
                score -= self.params["discard_penalty"]
            if tag in self.rules["interests"]:
                score += self.params["interest_bonus"]

        if self._match_deep_dive(title, tags):
            item["deep_dive"] = True

        item["score"] = max(0, min(100, score))
        return item["score"]

    def _match_deep_dive(self, title: str, tags: list[str]) -> bool:
        for trigger in self.rules["deep_dive_triggers"]:
            if trigger in title or any(trigger in tag for tag in tags):
                return True
        return False

    def classify_by_score(
        self, items: list[dict]
    ) -> tuple[list[dict], list[dict], list[dict]]:
        """Split items into deep (>=high), regular (low-high), discard (<low)."""
        high = self.params["high_threshold"]
        low = self.params["low_threshold"]
        deep = [i for i in items if i.get("score", 0) >= high]
        regular = [i for i in items if low <= i.get("score", 0) < high]
        discard = [i for i in items if i.get("score", 0) < low]
        return deep, regular, discard

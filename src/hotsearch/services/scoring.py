#!/usr/bin/env python3
"""Scoring service: compute weight scores for tagged items using tags + embeddings."""

import json
import re

from hotsearch import CONFIG_DIR
from hotsearch.config import prompt_templates


class ScoringService:
    """Pure algorithm: score items based on tag weights + embedding similarity."""

    def __init__(self):
        self.rules = self._load_scoring_rules()
        self.deep_dive_triggers = self._parse_deep_dive_triggers()
        self._top_tags = self._compute_top_tags()
        self._pref_text = prompt_templates().get("preference", "")
        self._pref_vec: list[float] | None = None

    def _load_scoring_rules(self) -> dict:
        path = CONFIG_DIR / "scoring_rules.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {
            "tags": {},
            "top_tags_count": 4,
            "top_deep_count": 5,
            "top_brief_count": 10,
            "embedding_weight": 0.3,
            "llm_refine_threshold": 60,
            "detail_threshold": 70,
            "high_threshold": 70,
            "low_threshold": 30,
        }

    def _compute_top_tags(self) -> set[str]:
        tags = self.rules.get("tags", {})
        count = self.rules.get("top_tags_count", 4)
        sorted_tags = sorted(tags.items(), key=lambda x: x[1], reverse=True)
        return set(name for name, _ in sorted_tags[:count])

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

    def _get_pref_vec(self) -> list[float]:
        if self._pref_vec is None:
            from hotsearch.tools.embedding import embed_doc

            self._pref_vec = embed_doc([self._pref_text])[0]
        return self._pref_vec

    def score(self, item: dict) -> int:
        """Compute score for a single tagged item. Mutates item in-place."""
        tags = item.get("tags", [])
        title = item.get("title", "")
        tag_weights = self.rules.get("tags", {})

        # Step A: max tag weight among item's tags
        tag_score = max((tag_weights.get(tag, 0) for tag in tags), default=0)

        # Step B: top-N tag filter
        if not any(tag in self._top_tags for tag in tags):
            item["score"] = 0
            return 0

        # Step C: embedding similarity
        try:
            from hotsearch.tools.embedding import embed_query, similarity

            title_vec = embed_query([title])[0]
            pref_vec = self._get_pref_vec()
            sim = similarity(title_vec, pref_vec)
            similarity_score = (sim + 1) / 2 * 100  # [-1, 1] -> [0, 100]
        except Exception:
            similarity_score = 50  # neutral fallback
        item["sim_score"] = int(similarity_score)

        # Step D: weighted combination
        w = self.rules.get("embedding_weight", 0.3)
        combined = tag_score * (1 - w) + similarity_score * w
        combined = max(0, min(100, combined))
        item["combined_score"] = int(combined)

        # Step E: final (will be refined by LLM later)
        item["score"] = item["combined_score"]

        # Deep dive flag
        if self._match_deep_dive(title, tags):
            item["deep_dive"] = True

        return item["score"]

    def _match_deep_dive(self, title: str, tags: list[str]) -> bool:
        for trigger in self.deep_dive_triggers:
            if trigger in title or any(trigger in tag for tag in tags):
                return True
        return False

    @property
    def llm_refine_threshold(self) -> int:
        return self.rules.get("llm_refine_threshold", 60)

    @property
    def top_deep_count(self) -> int:
        return self.rules.get("top_deep_count", 5)

    @property
    def top_brief_count(self) -> int:
        return self.rules.get("top_brief_count", 10)

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

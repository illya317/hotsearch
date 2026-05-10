#!/usr/bin/env python3
"""
Preference agent: manage user preferences for content filtering.

Usage:
    python3 -m hotsearch.agents.preference --summary
"""

import argparse

from hotsearch.config import prompt_templates
from hotsearch.llms import LLMClient, llm_for_agent


class PreferenceAgent:
    """Manage and apply user content preferences."""

    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm or llm_for_agent("preference")

    def load_preferences(self) -> str:
        """Load current preference markdown."""
        return prompt_templates().get("preference", "")

    def filter_items(self, items: list[dict]) -> tuple[list[dict], list[dict]]:
        """Return (keep, discard) based on user preferences.

        TODO: implement actual preference-based filtering logic.
        """
        return items, []

    def should_deep_dive(self, title: str, tags: list[str]) -> bool:
        """Determine if an item warrants deeper search based on preferences.

        TODO: read preference.md triggers and evaluate.
        """
        return False

    def summarize(self) -> str:
        """Return a readable summary of current preferences."""
        return self.load_preferences()


def main():
    ap = argparse.ArgumentParser(description="Preference agent")
    ap.add_argument("--summary", action="store_true", help="Show current preferences")
    args = ap.parse_args()

    agent = PreferenceAgent()

    if args.summary:
        print(agent.summarize())
        return

    ap.print_help()


if __name__ == "__main__":
    main()

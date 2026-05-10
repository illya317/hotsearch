#!/usr/bin/env python3
"""
Search agent: orchestrate search tools to enrich content.

Usage:
    python3 -m hotsearch.agents.search --query "keyword"
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from hotsearch.llms import LLMClient, llm_for_agent

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class SearchAgent:
    """Orchestrate Tavily/Exa searches based on content context."""

    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm or llm_for_agent("search")

    def should_search(self, title: str, tags: list[str]) -> bool:
        """Determine if a title warrants a background search.

        TODO: implement logic based on preference.md triggers.
        """
        return False

    def search_tavily(self, query: str, max_results: int = 5, **kwargs) -> dict:
        """Run Tavily search via CLI wrapper."""
        cmd = [
            sys.executable,
            "-m",
            "hotsearch.tools.system.tavily_search",
            "--query",
            query,
            "--max-results",
            str(max_results),
        ]
        if kwargs.get("save"):
            cmd.append("--save")
        if kwargs.get("search_depth"):
            cmd.extend(["--search-depth", kwargs["search_depth"]])
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(_PROJECT_ROOT),
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
            return {"error": result.stderr}
        except Exception as e:
            return {"error": str(e)}

    def search_exa(self, query: str, num_results: int = 5, **kwargs) -> dict:
        """Run Exa search via CLI wrapper."""
        cmd = [
            sys.executable,
            "-m",
            "hotsearch.tools.system.exa_search",
            "--query",
            query,
            "--num-results",
            str(num_results),
        ]
        if kwargs.get("save"):
            cmd.append("--save")
        if kwargs.get("type"):
            cmd.extend(["--type", kwargs["type"]])
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(_PROJECT_ROOT),
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
            return {"error": result.stderr}
        except Exception as e:
            return {"error": str(e)}

    def enrich_item(self, item: dict) -> dict:
        """Add search-enriched context to an item if warranted."""
        title = item.get("title", "")
        tags = item.get("tags", [])
        if self.should_search(title, tags):
            # TODO: generate search query and run
            pass
        return item


def main():
    ap = argparse.ArgumentParser(description="Search agent")
    ap.add_argument("--query", required=True, help="Search query")
    ap.add_argument("--tool", choices=["tavily", "exa"], default="tavily")
    ap.add_argument("--save", action="store_true", help="Save raw JSON")
    args = ap.parse_args()

    agent = SearchAgent()
    if args.tool == "tavily":
        result = agent.search_tavily(args.query, save=args.save)
    else:
        result = agent.search_exa(args.query, save=args.save)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

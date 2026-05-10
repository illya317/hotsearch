#!/usr/bin/env python3
"""
Tag agent: classify data from trends/feeds, detect uncertain items,
suggest rule updates, and self-modify TAG_RULES.

Usage:
    python3 -m hotsearch.agents.tag --check
    python3 -m hotsearch.agents.tag --update
    python3 -m hotsearch.agents.tag --apply
    python3 -m hotsearch.agents.tag --titles "标题1" "标题2"
"""

import argparse
import ast
import json
from pathlib import Path

import jinja2

from hotsearch.config import prompt_templates
from hotsearch.llms import LLMClient, llm_for_agent
from hotsearch.services.feeds import FeedsService
from hotsearch.services.trends import TrendsService
from hotsearch.tools.tag import TAG_RULES, classify

_templates = prompt_templates()
_jinja_env = jinja2.Environment(loader=jinja2.DictLoader(_templates))


def _render(name: str, **context) -> str:
    return _jinja_env.get_template(name).render(**context)


class TagAgent:
    """负责给数据打标签、检测标签质量、维护 TAG_RULES。"""

    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm or llm_for_agent("tag")

    def tag_all(self) -> dict:
        """Fetch trends + feeds, classify all items, collect uncertain titles."""
        trends = TrendsService().collect()
        feeds = FeedsService().collect()
        uncertain: list[str] = []

        for r in trends.get("results", []):
            if r.get("status") != "ok":
                continue
            for title in self._extract_titles(r.get("data", {})):
                if "uncertain" in classify(title):
                    uncertain.append(title)

        for r in feeds.get("results", []):
            if r.get("status") != "ok":
                continue
            for title in self._extract_titles(r.get("data", {})):
                if "uncertain" in classify(title):
                    uncertain.append(title)

        return {"trends": trends, "feeds": feeds, "uncertain": uncertain}

    @staticmethod
    def _extract_titles(data: dict) -> list[str]:
        """Extract titles from standardized data format."""
        titles: list[str] = []
        for item in data.get("items", []):
            t = item.get("title", "")
            if t:
                titles.append(t)
        return titles

    def suggest_rule_updates(self, titles: list[str]) -> dict:
        """Ask LLM for TAG_RULES updates."""
        prompt = _render(
            "tag",
            rules=json.dumps(TAG_RULES, ensure_ascii=False, indent=2),
            titles=titles,
        )
        messages = [
            {"role": "system", "content": "你是一个专注中文内容分类的助手。"},
            {"role": "user", "content": prompt},
        ]
        raw = self.llm.chat(messages, max_tokens=2048)

        # Try to extract JSON from markdown code block or plain text
        text = raw.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        try:
            return json.loads(text.strip())
        except Exception as e:
            return {"error": str(e), "raw": raw}

    def classify_with_llm(self, title: str) -> list[str]:
        """LLM fallback classification when keywords miss."""
        prompt = _render(
            "tag_classify",
            tags=", ".join(TAG_RULES.keys()),
            title=title,
        )
        messages = [
            {
                "role": "system",
                "content": "你是一个专注中文内容分类的助手。只输出 JSON 数组。",
            },
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

    def update_rules(
        self,
        updates: dict[str, list[str]],
        new_tags: dict[str, list[str]] | None = None,
    ) -> None:
        """Merge LLM-suggested updates into TAG_RULES and write back to tools/tag.py."""
        new_rules = dict(TAG_RULES)

        for tag, keywords in updates.items():
            if tag in new_rules:
                existing = set(new_rules[tag])
                existing.update(keywords)
                new_rules[tag] = sorted(existing)
            else:
                new_rules[tag] = sorted(keywords)

        if new_tags:
            for tag, keywords in new_tags.items():
                if tag not in new_rules:
                    new_rules[tag] = sorted(keywords)

        _rewrite_tag_file(new_rules)


def _rewrite_tag_file(new_rules: dict[str, list[str]]) -> None:
    """Rewrite tools/tag.py with new TAG_RULES, preserving other code."""
    tag_path = Path(__file__).resolve().parent.parent / "tools" / "tag.py"
    source = tag_path.read_text(encoding="utf-8")

    # Try AST-based replacement to preserve surrounding code
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "TAG_RULES":
                        start = node.lineno - 1
                        end = getattr(node, "end_lineno", start + 1)
                        lines = source.splitlines()
                        prefix = "\n".join(lines[:start]) + "\n"
                        suffix = (
                            "\n" + "\n".join(lines[end:]) if end < len(lines) else ""
                        )
                        rules_json = json.dumps(new_rules, ensure_ascii=False, indent=4)
                        new_assign = f"TAG_RULES: dict[str, list[str]] = {rules_json}"
                        tag_path.write_text(
                            prefix + new_assign + suffix, encoding="utf-8"
                        )
                        return
    except Exception:
        pass

    # Fallback: full rewrite
    content = (
        '"""内容标签分类规则。通过关键词匹配给标题自动打标签。"""\n\n'
        f"TAG_RULES: dict[str, list[str]] = {json.dumps(new_rules, ensure_ascii=False, indent=4)}\n\n\n"
        "def classify(title: str) -> list[str]:\n"
        '    """根据标题匹配标签。未匹配到任何标签时返回 [\'uncertain\']。"""\n'
        "    matched: list[str] = []\n"
        "    for tag, keywords in TAG_RULES.items():\n"
        "        for kw in keywords:\n"
        "            if kw in title:\n"
        "                matched.append(tag)\n"
        "                break\n"
        '    return matched if matched else ["uncertain"]\n'
    )
    tag_path.write_text(content, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Tag agent")
    ap.add_argument(
        "--check", action="store_true", help="Check all data and report uncertain items"
    )
    ap.add_argument(
        "--update", action="store_true", help="Suggest rule updates for uncertain items"
    )
    ap.add_argument(
        "--apply", action="store_true", help="Apply LLM-suggested updates to TAG_RULES"
    )
    ap.add_argument("--titles", nargs="+", help="Classify specific titles")
    args = ap.parse_args()

    agent = TagAgent()

    if args.titles:
        for title in args.titles:
            tags = classify(title)
            if "uncertain" in tags:
                tags = agent.classify_with_llm(title)
            print(f"{title} -> {tags}")
        return

    if args.check or args.update or args.apply:
        result = agent.tag_all()
        uncertain = result["uncertain"]
        print(f"Total uncertain items: {len(uncertain)}")
        for t in uncertain[:20]:
            print(f"  - {t}")

        if uncertain and (args.update or args.apply):
            suggestion = agent.suggest_rule_updates(uncertain[:50])
            print(json.dumps(suggestion, ensure_ascii=False, indent=2))

            if args.apply and "updates" in suggestion:
                updates = suggestion.get("updates", {})
                new_tags = suggestion.get("new_tags", {})
                agent.update_rules(updates, new_tags)
                print("TAG_RULES updated.")
        return

    ap.print_help()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Search service: unified Tavily + Exa search with dedup and domain filtering."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from hotsearch import CACHE_SEARCH_DIR, CONFIG_DIR
from hotsearch.tools.logger import get_logger

_log = get_logger("search")


def _load_domain_filters() -> tuple[set[str], set[str]]:
    path = CONFIG_DIR / "search_sources.json"
    if not path.exists():
        return set(), set()
    cfg = json.loads(path.read_text(encoding="utf-8"))
    trusted = {_extract_domain(d) for d in cfg.get("trusted_domains", [])}
    blocked = {_extract_domain(d) for d in cfg.get("blocked_domains", [])}
    return trusted, blocked


def _extract_domain(url: str) -> str:
    try:
        return (
            urlparse(url if "://" in url else f"https://{url}")
            .netloc.lower()
            .lstrip("www.")
        )
    except Exception:
        return url.lower()


def _to_markdown(results: list[dict], query: str) -> str:
    lines = [f"# Search: {query}\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title") or r.get("url") or "(no title)"
        url = r.get("url", "")
        snippet = r.get("snippet", "") or r.get("content", "")
        source = r.get("source", "")
        lines.append(f"## {i}. {title}")
        if url:
            lines.append(f"  {url}")
        if snippet:
            lines.append(f"  > {snippet[:300]}")
        if source:
            lines.append(f"  _source: {source}_")
        lines.append("")
    return "\n".join(lines)


_JUNK_PATTERNS = [
    "郑重声明", "代客理财", "免费荐股", "炒股培训", "非法证券",
    "不代表本网站立场", "据此操作风险自担", "财富号", "股吧",
    "评论", "分享至", "朋友圈", "微博",
]


class SearchService:
    """Unified search across Tavily and Exa."""

    def __init__(self):
        self.trusted_domains, self.blocked_domains = _load_domain_filters()

    def search(
        self,
        query: str,
        engines: list[str] | None = None,
        max_results: int = 5,
        save: bool = True,
        force: bool = False,
    ) -> dict:
        """Run search across engines, dedup, filter, return aggregated results."""
        if engines is None:
            engines = ["tavily", "exa"]

        # Check cache first
        if not force:
            cached = self._load_cache(query)
            if cached is not None:
                _log.info("search '%s': %d results from cache", query, len(cached.get("results", [])))
                return cached

        all_results: list[dict] = []
        with ThreadPoolExecutor() as pool:
            futures = {}
            if "tavily" in engines:
                futures[pool.submit(self._search_tavily, query, max_results)] = "tavily"
            if "exa" in engines:
                futures[pool.submit(self._search_exa, query, max_results)] = "exa"

            for future in as_completed(futures):
                source = futures[future]
                try:
                    results = future.result()
                    for r in results:
                        r["source"] = source
                    all_results.extend(results)
                except Exception as e:
                    _log.error("search %s failed: %s", source, e)

        deduped = self._deduplicate(all_results)
        filtered = self._filter_domains(deduped)
        ranked = self._rank_by_trust(filtered)

        output = {
            "query": query,
            "results": ranked[:max_results],
            "engines_used": engines,
            "total_found": len(ranked),
        }

        if save and ranked:
            md = _to_markdown(ranked[:max_results], query)
            self._save_md(query, md)
            self._save_cache(query, output)

        _log.info("search '%s': %d results from %s", query, len(ranked), engines)
        return output

    def enrich_item(self, item: dict, max_results: int = 3) -> dict:
        """Search for an item's title and attach search context."""
        title = item.get("title", "")
        if not title:
            return item
        result = self.search(title, max_results=max_results, save=True)
        item["search_context"] = self._format_context(result["results"])
        return item

    def _search_tavily(self, query: str, max_results: int) -> list[dict]:
        from hotsearch.tools.system.tavily_search import tavily_search

        result = tavily_search(
            query, max_results, include_answer=False, search_depth="basic"
        )
        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
            }
            for r in result.get("results", [])
        ]
        return [r for r in results if self._is_quality_snippet(r.get("snippet", ""))]

    def _search_exa(self, query: str, max_results: int) -> list[dict]:
        from hotsearch.tools.system.exa_search import search_all

        result = search_all(query, max_results, "auto", 0, False)
        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": (r.get("text") or "")[:300],
            }
            for r in result.get("results", [])
        ]
        return [r for r in results if self._is_quality_snippet(r.get("snippet", ""))]

    @staticmethod
    def _is_quality_snippet(snippet: str) -> bool:
        """Filter out low-quality snippets (ads, forums, disclaimers)."""
        if not snippet or len(snippet) < 20:
            return False
        for pattern in _JUNK_PATTERNS:
            if pattern in snippet:
                return False
        # Too many special chars = likely navigation/formatting junk
        special = sum(1 for c in snippet if c in "#*|_=[]{}")
        if special > len(snippet) * 0.15:
            return False
        return True

    def _deduplicate(self, results: list[dict]) -> list[dict]:
        seen: set[str] = set()
        out = []
        for r in results:
            url = r.get("url", "")
            if url and url in seen:
                continue
            seen.add(url)
            out.append(r)
        return out

    def _filter_domains(self, results: list[dict]) -> list[dict]:
        if not self.blocked_domains:
            return results
        return [
            r
            for r in results
            if _extract_domain(r.get("url", "")) not in self.blocked_domains
        ]

    def _rank_by_trust(self, results: list[dict]) -> list[dict]:
        trusted = []
        rest = []
        for r in results:
            domain = _extract_domain(r.get("url", ""))
            if domain in self.trusted_domains:
                trusted.append(r)
            else:
                rest.append(r)
        return trusted + rest

    def _format_context(self, results: list[dict]) -> str:
        lines = []
        for r in results[:3]:
            title = self._clean_text(r.get("title", ""))[:80]
            snippet = self._clean_text(r.get("snippet", ""))
            if not snippet:
                continue
            if len(snippet) > 30:
                lines.append(f"  · {title}\n    {snippet[:120]}")
            else:
                lines.append(f"  · {title}: {snippet}")
        return "\n".join(lines) if lines else ""

    def _cache_key(self, query: str) -> str:
        return hashlib.md5(query.encode()).hexdigest()[:16]

    def _load_cache(self, query: str) -> dict | None:
        path = CACHE_SEARCH_DIR / f"search_{self._cache_key(query)}.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None

    def _save_cache(self, query: str, data: dict) -> Path:
        CACHE_SEARCH_DIR.mkdir(parents=True, exist_ok=True)
        path = CACHE_SEARCH_DIR / f"search_{self._cache_key(query)}.json"
        payload = {
            "query": query,
            "time": datetime.now().isoformat(),
            "results": data["results"],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def _save_md(self, query: str, md: str) -> Path:
        CACHE_SEARCH_DIR.mkdir(parents=True, exist_ok=True)
        key = hashlib.md5(query.encode()).hexdigest()[:16]
        path = CACHE_SEARCH_DIR / f"search_{key}.md"
        payload = f"<!-- query: {query} -->\n<!-- time: {datetime.now().isoformat()} -->\n\n{md}"
        path.write_text(payload, encoding="utf-8")
        return path

    @staticmethod
    def _clean_text(text: str) -> str:
        """Remove HTML entities and normalize whitespace in search result text."""
        import re
        text = re.sub(r"&[a-z]+;", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

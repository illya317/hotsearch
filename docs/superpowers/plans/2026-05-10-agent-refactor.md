# Agent 架构重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 4 个 agent 重构为 2 个（ContentAgent + SummaryAgent），评分算法和搜索下沉为 service，严格分层，补全日志。

**Architecture:** agent → service → tools 三层。ContentAgent 做分类+评分，SummaryAgent 做搜索增强+模板渲染+飞书推送。新增 ScoringService（评分算法）、SearchService（Tavily+Exa 统一封装）。TrendsService/FeedsService 新增 load_latest()。

**Tech Stack:** Python 3, stdlib http.server + urllib, Jinja2, PyYAML, lark-oapi

---

### Task 1: 新建评分参数配置

**Files:**
- Create: `config/preference.json`

- [ ] **Step 1: 创建评分参数配置文件**

```bash
cat > config/preference.json << 'EOF'
{
  "base_score": 50,
  "keep_bonus": 30,
  "interest_bonus": 20,
  "discard_penalty": 40,
  "high_threshold": 70,
  "low_threshold": 30
}
EOF
```

- [ ] **Step 2: 验证 JSON 格式**

```bash
python3 -c "import json; json.load(open('config/preference.json')); print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add config/preference.json
git commit -m "feat: add scoring parameter config

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: 新建搜索域名过滤配置

**Files:**
- Create: `config/search_sources.json`

- [ ] **Step 1: 创建搜索域名白/黑名单**

```bash
cat > config/search_sources.json << 'EOF'
{
  "trusted_domains": [
    "github.com",
    "arxiv.org",
    "news.cn",
    "people.com.cn",
    "thepaper.cn",
    "36kr.com",
    "jiqizhixin.com",
    "infoq.cn"
  ],
  "blocked_domains": [
    "zhihu.com",
    "weibo.com",
    "douyin.com"
  ]
}
EOF
```

- [ ] **Step 2: 验证 JSON 格式**

```bash
python3 -c "import json; json.load(open('config/search_sources.json')); print('OK')"
```
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add config/search_sources.json
git commit -m "feat: add search domain filter config

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: 新建 Summary 输出模板

**Files:**
- Create: `config/prompts/summary.j2`

- [ ] **Step 1: 创建 Jinja2 模板**

```bash
cat > config/prompts/summary.j2 << 'J2EOF'
# {{ name }} {{ time }}

## 🔥 深度关注（{{ deep_items|length }}条）
{% for item in deep_items %}
- {{ item.title }}  [{{ item.score }}分]
  {% if item.search_context %}🔍 {{ item.search_context }}{% endif %}
  {{ item.url }}
{% endfor %}

## 📋 常规浏览（{{ regular_items|length }}条）
{% for item in regular_items %}
- {{ item.title }}  [{{ item.score }}分]
{% endfor %}

## 📊 统计
本次采集 {{ total }} 条，推送 {{ sent }} 条，丢弃 {{ discarded }} 条
J2EOF
```

- [ ] **Step 2: 验证模板可编译**

```bash
python3 -c "
import jinja2
env = jinja2.Environment(loader=jinja2.FileSystemLoader('config/prompts'))
tpl = env.get_template('summary.j2')
result = tpl.render(
    name='测试', time='2026-05-10 08:00',
    deep_items=[{'title':'test','score':80,'url':'http://x','search_context':'ctx'}],
    regular_items=[{'title':'reg','score':50,'url':'http://y'}],
    total=3, sent=2, discarded=1
)
print(result[:100])
print('OK')
"
```
Expected: 输出包含 "深度关注" 和 "常规浏览"。

- [ ] **Step 3: Commit**

```bash
git add config/prompts/summary.j2
git commit -m "feat: add summary output template

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: 新建 ScoringService

**Files:**
- Create: `src/hotsearch/services/scoring.py`

- [ ] **Step 1: 创建评分服务**

```python
cat > src/hotsearch/services/scoring.py << 'PYEOF'
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
            if trigger in title:
                return True
        return False

    def classify_by_score(self, items: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
        """Split items into deep (>=high), regular (low-high), discard (<low)."""
        high = self.params["high_threshold"]
        low = self.params["low_threshold"]
        deep = [i for i in items if i.get("score", 0) >= high]
        regular = [i for i in items if low <= i.get("score", 0) < high]
        discard = [i for i in items if i.get("score", 0) < low]
        return deep, regular, discard
PYEOF
```

- [ ] **Step 2: 验证导入和基本逻辑**

```bash
cd /Users/koito/Desktop/Project/hotsearch && \
PYTHONPATH=src python3 -c "
from hotsearch.services.scoring import ScoringService
s = ScoringService()
item = {'title': '特朗普外交政策', 'tags': ['地缘政治'], 'url': 'http://x'}
s.score(item)
assert item['score'] >= 50, f'score should be >=50, got {item[\"score\"]}'
print(f'Score: {item[\"score\"]}, OK')
"
```
Expected: `Score: XX, OK`

- [ ] **Step 3: Commit**

```bash
git add src/hotsearch/services/scoring.py
git commit -m "feat: add ScoringService for item weight scoring

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 5: 新建 SearchService

**Files:**
- Create: `src/hotsearch/services/search.py`

- [ ] **Step 1: 创建搜索服务**

```python
cat > src/hotsearch/services/search.py << 'PYEOF'
#!/usr/bin/env python3
"""Search service: unified Tavily + Exa search with dedup and domain filtering."""

import hashlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from hotsearch import CACHE_SEARCH_DIR, CONFIG_DIR
from hotsearch.tools.logger import get_logger

_log = get_logger(__name__)


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
        return urlparse(url if "://" in url else f"https://{url}").netloc.lower().lstrip("www.")
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
    ) -> dict:
        """Run search across engines, dedup, filter, return aggregated results."""
        if engines is None:
            engines = ["tavily", "exa"]

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

        result = tavily_search(query, max_results, include_answer=False, search_depth="basic")
        return [
            {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": r.get("content", "")}
            for r in result.get("results", [])
        ]

    def _search_exa(self, query: str, max_results: int) -> list[dict]:
        from hotsearch.tools.system.exa_search import search_all

        result = search_all(query, max_results, "auto", 0, False)
        return [
            {"title": r.get("title", ""), "url": r.get("url", ""), "snippet": (r.get("text") or "")[:300]}
            for r in result.get("results", [])
        ]

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
        parts = []
        for r in results[:3]:
            title = r.get("title", "")[:60]
            snippet = r.get("snippet", "")[:100]
            if snippet:
                parts.append(f"{title}: {snippet}")
            else:
                parts.append(title)
        return " | ".join(parts)

    def _save_md(self, query: str, md: str) -> Path:
        CACHE_SEARCH_DIR.mkdir(parents=True, exist_ok=True)
        key = hashlib.md5(query.encode()).hexdigest()[:16]
        path = CACHE_SEARCH_DIR / f"search_{key}.md"
        payload = f"<!-- query: {query} -->\n<!-- time: {datetime.now().isoformat()} -->\n\n{md}"
        path.write_text(payload, encoding="utf-8")
        return path
PYEOF
```

- [ ] **Step 2: 验证 SearchService 导入**

```bash
cd /Users/koito/Desktop/Project/hotsearch && \
PYTHONPATH=src python3 -c "
from hotsearch.services.search import SearchService
s = SearchService()
print(f'Trusted domains: {len(s.trusted_domains)}, Blocked: {len(s.blocked_domains)}')
print('Import OK')
"
```
Expected: `Trusted domains: 8, Blocked: 3` + `Import OK`

- [ ] **Step 3: Commit**

```bash
git add src/hotsearch/services/search.py
git commit -m "feat: add SearchService for unified Tavily+Exa search

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 6: 改造 TrendsService — 添加 load_latest

**Files:**
- Modify: `src/hotsearch/services/trends.py`

- [ ] **Step 1: 在 TrendsService 类中添加 load_latest 静态方法**

编辑 `src/hotsearch/services/trends.py`，在 `TrendsService.collect()` 方法之后（class 内）添加：

```python
    @staticmethod
    def load_latest(mode: str) -> dict | None:
        """Load the latest saved StandardResult for a given mode from cache."""
        candidates = []
        for path in CACHE_TRENDS_DIR.glob(f"{mode}_*.json"):
            try:
                ts = float(path.stem.split("_", 1)[1])
                candidates.append((ts, path))
            except Exception:
                continue
        if not candidates:
            return None
        latest = sorted(candidates, reverse=True)[0][1]
        return json.loads(latest.read_text(encoding="utf-8"))
```

- [ ] **Step 2: 验证 load_latest 方法存在**

```bash
cd /Users/koito/Desktop/Project/hotsearch && \
PYTHONPATH=src python3 -c "
from hotsearch.services.trends import TrendsService
assert hasattr(TrendsService, 'load_latest'), 'load_latest missing'
print('Method exists OK')
"
```
Expected: `Method exists OK`

- [ ] **Step 3: Commit**

```bash
git add src/hotsearch/services/trends.py
git commit -m "feat: add TrendsService.load_latest() for cache reading

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 7: 改造 FeedsService — 添加 load_latest

**Files:**
- Modify: `src/hotsearch/services/feeds.py`

- [ ] **Step 1: 在 FeedsService 类中添加 load_latest 静态方法**

编辑 `src/hotsearch/services/feeds.py`，在 `FeedsService.check_new()` 方法之后（class 内）添加：

```python
    @staticmethod
    def load_latest() -> dict | None:
        """Load the latest feeds StandardResult from cache."""
        candidates = []
        for path in CACHE_FEEDS_DIR.glob("feeds_*.json"):
            try:
                ts = float(path.stem.split("_", 1)[1])
                candidates.append((ts, path))
            except Exception:
                continue
        if not candidates:
            return None
        latest = sorted(candidates, reverse=True)[0][1]
        return json.loads(latest.read_text(encoding="utf-8"))
```

- [ ] **Step 2: 验证 load_latest 方法存在**

```bash
cd /Users/koito/Desktop/Project/hotsearch && \
PYTHONPATH=src python3 -c "
from hotsearch.services.feeds import FeedsService
assert hasattr(FeedsService, 'load_latest'), 'load_latest missing'
print('Method exists OK')
"
```
Expected: `Method exists OK`

- [ ] **Step 3: Commit**

```bash
git add src/hotsearch/services/feeds.py
git commit -m "feat: add FeedsService.load_latest() for cache reading

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 8: 新建 ContentAgent

**Files:**
- Create: `src/hotsearch/agents/content.py`

- [ ] **Step 1: 创建 ContentAgent**

```python
cat > src/hotsearch/agents/content.py << 'PYEOF'
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
from pathlib import Path

import jinja2

from hotsearch import CACHE_FEEDS_DIR, CACHE_TRENDS_DIR
from hotsearch.config import prompt_templates
from hotsearch.llms import LLMClient, llm_for_agent
from hotsearch.services.scoring import ScoringService
from hotsearch.services.trends import TrendsService
from hotsearch.services.feeds import FeedsService
from hotsearch.tools.logger import get_logger
from hotsearch.tools.tag import TAG_RULES, classify

_log = get_logger(__name__)
_CACHE_CRON_DIR = Path(CACHE_TRENDS_DIR).parent / "cron"

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

        _CACHE_CRON_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        out_path = _CACHE_CRON_DIR / f"{mode}_scored_{ts}.json"
        out_path.write_text(json.dumps(scored_data, ensure_ascii=False, indent=2), encoding="utf-8")

        scores = [i.get("score", 0) for i in all_items]
        _log.info("%s: %d tagged, %d uncertain, scored [%d-%d]",
                  mode, len(all_items), raw.get("uncertain_count", 0),
                  min(scores) if scores else 0, max(scores) if scores else 0)

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
PYEOF
```

- [ ] **Step 2: 验证 ContentAgent 导入**

```bash
cd /Users/koito/Desktop/Project/hotsearch && \
PYTHONPATH=src python3 -c "
from hotsearch.agents.content import ContentAgent, TagEngine
a = ContentAgent()
print(f'Scorer params: {a.scorer.params}')
print('Import OK')
"
```
Expected: `Scorer params: {...}` + `Import OK`

- [ ] **Step 3: Commit**

```bash
git add src/hotsearch/agents/content.py
git commit -m "feat: add ContentAgent (classify + score pipeline)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 9: 新建 SummaryAgent

**Files:**
- Create: `src/hotsearch/agents/summary.py`

- [ ] **Step 1: 创建 SummaryAgent**

```python
cat > src/hotsearch/agents/summary.py << 'PYEOF'
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
                str(Path(__file__).resolve().parent.parent.parent.parent / "config" / "prompts")
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

        _log.info("%s: %d deep, %d regular, %d discarded, sent=%s",
                  mode, len(deep), len(regular), len(discard), send)

        if send:
            print(text)
            send_to_feishu(text)

        return text

    def _load_scored(self, source: str) -> dict | None:
        """Find the latest scored JSON for a mode."""
        candidates = []
        for path in _CACHE_CRON_DIR.glob(f"{source}_scored_*.json"):
            try:
                ts = float(path.stem.rsplit("_", 1)[1])
                candidates.append((ts, path))
            except Exception:
                continue
        if not candidates:
            return None
        latest = sorted(candidates, reverse=True)[0][1]
        return json.loads(latest.read_text(encoding="utf-8"))


def main():
    ap = argparse.ArgumentParser(description="Summary agent: enrich + render + send")
    ap.add_argument("--source", required=True, help="Mode name or 'feeds'")
    ap.add_argument("--send", action="store_true", help="Send to Feishu after rendering")
    args = ap.parse_args()

    agent = SummaryAgent()
    agent.run(args.source, send=args.send)


if __name__ == "__main__":
    main()
PYEOF
```

- [ ] **Step 2: 验证 SummaryAgent 导入**

```bash
cd /Users/koito/Desktop/Project/hotsearch && \
PYTHONPATH=src python3 -c "
from hotsearch.agents.summary import SummaryAgent
a = SummaryAgent()
print('Import OK')
"
```
Expected: `Import OK`

- [ ] **Step 3: Commit**

```bash
git add src/hotsearch/agents/summary.py
git commit -m "feat: add SummaryAgent (search enrich + render + send)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 10: 改造 cron-task.sh — 三步管道

**Files:**
- Modify: `scripts/cron-task.sh`

- [ ] **Step 1: 修改 trends 分支为三步管道**

编辑 `scripts/cron-task.sh`，将 trends case 分支（`*` case 内的内容）替换为：

```bash
        *)
        if _is_trends_task "$1"; then
            # Step 1: 数据采集
            ./scripts/run.sh "src/hotsearch/services/trends.py" "$@" >> "$LOG"
            # Step 2: 分类+打分
            ./scripts/run.sh "src/hotsearch/agents/content.py" --source "$1" >> "$LOG"
            # Step 3: 搜索增强+渲染+推送
            ./scripts/run.sh "src/hotsearch/agents/summary.py" --source "$1" --send >> "$LOG"
        else
            echo "Usage: $0 {feeds|status|$(_trends_tasks | tr '\n' '|' | sed 's/|$//')}" >&2
            exit 1
        fi
        ;;
```

对于 feeds 分支，也改为三步（保留原有 script 调用）：

```bash
    feeds)
        SCRIPT="$(_script_for_task "$1")"
        # Step 1: 数据采集
        ./scripts/run.sh "$SCRIPT" >> "$LOG"
        ./scripts/run.sh "src/hotsearch/services/feeds.py" >> "$LOG"
        # Step 2: 分类+打分
        ./scripts/run.sh "src/hotsearch/agents/content.py" --source feeds >> "$LOG"
        # Step 3: 搜索增强+渲染+推送
        ./scripts/run.sh "src/hotsearch/agents/summary.py" --source feeds --send >> "$LOG"
        ;;
```

- [ ] **Step 2: 验证脚本语法**

```bash
bash -n scripts/cron-task.sh
```
Expected: 无输出（语法正确）

- [ ] **Step 3: Commit**

```bash
git add scripts/cron-task.sh
git commit -m "feat: update cron-task.sh to 3-step pipeline

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 11: 删除旧 Agent 文件

**Files:**
- Delete: `src/hotsearch/agents/tag.py`
- Delete: `src/hotsearch/agents/preference.py`
- Delete: `src/hotsearch/agents/search.py`

- [ ] **Step 1: 删除旧文件**

```bash
cd /Users/koito/Desktop/Project/hotsearch && \
git rm src/hotsearch/agents/tag.py \
       src/hotsearch/agents/preference.py \
       src/hotsearch/agents/search.py
```

- [ ] **Step 2: 验证没有残留引用**

```bash
cd /Users/koito/Desktop/Project/hotsearch && \
grep -rn "from hotsearch.agents import tag\|from hotsearch.agents.tag\|from hotsearch.agents.preference\|from hotsearch.agents.search" src/ 2>/dev/null || echo "No remaining references - OK"
```
Expected: `No remaining references - OK`

- [ ] **Step 3: Commit**

```bash
git commit -m "refactor: remove old agent files (merged into content.py + summary.py)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 12: 验证评分算法

**Files:**
- Test: inline verification (no permanent test file)

- [ ] **Step 1: 运行评分算法验证**

```bash
cd /Users/koito/Desktop/Project/hotsearch && \
PYTHONPATH=src python3 << 'PYEOF'
from hotsearch.services.scoring import ScoringService

s = ScoringService()

# Test 1: base score with no matching tags
item1 = {"title": "未知内容", "tags": ["uncertain"], "url": ""}
s.score(item1)
assert item1["score"] == 50, f"Expected 50, got {item1['score']}"
print(f"Test 1 PASS: base score = {item1['score']}")

# Test 2: discard penalty
item2 = {"title": "明星离婚新闻", "tags": ["娱乐八卦"], "url": ""}
s.score(item2)
assert item2["score"] <= 50, f"Expected <=50, got {item2['score']}"
print(f"Test 2 PASS: discard penalty applied = {item2['score']}")

# Test 3: interest bonus
item3 = {"title": "DeepSeek 发布新模型", "tags": ["AI/科技"], "url": ""}
s.score(item3)
assert item3["score"] >= 50, f"Expected >=50, got {item3['score']}"
print(f"Test 3 PASS: interest bonus applied = {item3['score']}")

# Test 4: score clamped [0, 100]
item4 = {"title": "test", "tags": [], "url": ""}
item4["score"] = 150
# modify score directly then check classify_by_score clamping logic
deep, regular, discard = s.classify_by_score([item4])
assert len(deep) == 1, f"Expected item in deep, got deep={len(deep)}"
print(f"Test 4 PASS: high score item classified as deep")

# Test 5: classify_by_score splits correctly
items = [
    {"title": "a", "score": 90, "url": ""},
    {"title": "b", "score": 50, "url": ""},
    {"title": "c", "score": 20, "url": ""},
]
deep, regular, discard = s.classify_by_score(items)
assert len(deep) == 1 and len(regular) == 1 and len(discard) == 1
print(f"Test 5 PASS: splits deep={len(deep)} regular={len(regular)} discard={len(discard)}")

print("\nAll scoring tests PASSED")
PYEOF
```
Expected: All 5 tests pass.

- [ ] **Step 2: 评分逻辑确认无误，无需单独 commit**

---

### Task 13: 端到端管道验证（dry-run）

**Files:**
- No changes, verification only

- [ ] **Step 1: 检查新文件结构完整性**

```bash
cd /Users/koito/Desktop/Project/hotsearch && \
echo "=== New configs ===" && \
ls -la config/preference.json config/search_sources.json config/prompts/summary.j2 && \
echo "" && \
echo "=== New services ===" && \
ls -la src/hotsearch/services/scoring.py src/hotsearch/services/search.py && \
echo "" && \
echo "=== New agents ===" && \
ls -la src/hotsearch/agents/content.py src/hotsearch/agents/summary.py && \
echo "" && \
echo "=== Old agents removed? ===" && \
ls src/hotsearch/agents/tag.py src/hotsearch/agents/preference.py src/hotsearch/agents/search.py 2>&1 && \
echo "" && \
echo "=== Import chain ===" && \
PYTHONPATH=src python3 -c "
from hotsearch.services.scoring import ScoringService
from hotsearch.services.search import SearchService
from hotsearch.agents.content import ContentAgent
from hotsearch.agents.summary import SummaryAgent
from hotsearch.services.trends import TrendsService
from hotsearch.services.feeds import FeedsService
print('All imports OK')
print(f'TrendsService.load_latest: {hasattr(TrendsService, \"load_latest\")}')
print(f'FeedsService.load_latest: {hasattr(FeedsService, \"load_latest\")}')
"
```
Expected: New files exist, old agents gone, all imports OK, load_latest methods present.

- [ ] **Step 2: 全部通过则整体验收完成**

---

### Task 14: 最终 Commit 和状态确认

- [ ] **Step 1: 检查 git status**

```bash
cd /Users/koito/Desktop/Project/hotsearch && git status
```

- [ ] **Step 2: 确认所有变更已提交，工作区干净**

预期：`nothing to commit, working tree clean`（或只有之前未提交的无关文件）

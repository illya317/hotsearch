#!/usr/bin/env python3
import argparse
import json
import os
import pathlib
import re
import sys
import urllib.request

TAVILY_URL = "https://api.tavily.com/search"


def load_key():
    # Try primary key first
    key = os.environ.get("TAVILY_API_KEY")
    if key:
        return key.strip(), "primary"

    # Try backup key
    key = os.environ.get("TAVILY_API_KEY_BACKUP")
    if key:
        return key.strip(), "backup"

    env_path = pathlib.Path.home() / ".openclaw" / ".env"
    if env_path.exists():
        try:
            txt = env_path.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"^\s*TAVILY_API_KEY\s*=\s*(.+?)\s*$", txt, re.M)
            if m:
                v = m.group(1).strip().strip('"').strip("'")
                if v:
                    return v, "primary"
            # Try backup in env file
            m = re.search(r"^\s*TAVILY_API_KEY_BACKUP\s*=\s*(.+?)\s*$", txt, re.M)
            if m:
                v = m.group(1).strip().strip('"').strip("'")
                if v:
                    return v, "backup"
        except Exception:
            pass

    return None, None


def tavily_search(query: str, max_results: int, include_answer: bool, search_depth: str):
    key, key_type = load_key()
    if not key:
        raise SystemExit(
            "Missing TAVILY_API_KEY. Set env var TAVILY_API_KEY or add it to ~/.openclaw/.env"
        )

    # Try search with primary key, fallback to backup on failure
    result = _do_search(query, max_results, include_answer, search_depth, key)
    if result is None and key_type == "primary":
        # Try backup key
        backup_key = os.environ.get("TAVILY_API_KEY_BACKUP")
        if backup_key:
            result = _do_search(query, max_results, include_answer, search_depth, backup_key.strip())

    if result is None:
        raise SystemExit("Search failed with both primary and backup keys")

    return result


def _do_search(query: str, max_results: int, include_answer: bool, search_depth: str, api_key: str):
    """Internal search function, returns None on failure."""

    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": search_depth,
        "include_answer": bool(include_answer),
        "include_images": False,
        "include_raw_content": False,
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        TAVILY_URL,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8", errors="replace")

    try:
        obj = json.loads(body)
    except json.JSONDecodeError:
        raise SystemExit(f"Tavily returned non-JSON: {body[:300]}")

    out = {
        "query": query,
        "answer": obj.get("answer"),
        "results": [],
    }

    for r in (obj.get("results") or [])[:max_results]:
        out["results"].append(
            {
                "title": r.get("title"),
                "url": r.get("url"),
                "content": r.get("content"),
            }
        )

    if not include_answer:
        out.pop("answer", None)

    return out

    return None


def to_brave_like(obj: dict) -> dict:
    # A lightweight, stable shape similar to web_search: results with title/url/snippet.
    results = []
    for r in obj.get("results", []) or []:
        results.append(
            {
                "title": r.get("title"),
                "url": r.get("url"),
                "snippet": r.get("content"),
            }
        )
    out = {"query": obj.get("query"), "results": results}
    if "answer" in obj:
        out["answer"] = obj.get("answer")
    return out


def to_markdown(obj: dict) -> str:
    lines = []
    if obj.get("answer"):
        lines.append(obj["answer"].strip())
        lines.append("")
    for i, r in enumerate(obj.get("results", []) or [], 1):
        title = (r.get("title") or "").strip() or r.get("url") or "(no title)"
        url = r.get("url") or ""
        snippet = (r.get("content") or "").strip()
        lines.append(f"{i}. {title}")
        if url:
            lines.append(f"   {url}")
        if snippet:
            lines.append(f"   - {snippet}")
    return "\n".join(lines).strip() + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--max-results", type=int, default=5)
    ap.add_argument("--include-answer", action="store_true")
    ap.add_argument(
        "--search-depth",
        default="basic",
        choices=["basic", "advanced"],
        help="Tavily search depth",
    )
    ap.add_argument(
        "--format",
        default="raw",
        choices=["raw", "brave", "md"],
        help="Output format: raw (default) | brave (title/url/snippet) | md (human-readable)",
    )
    args = ap.parse_args()

    res = tavily_search(
        query=args.query,
        max_results=max(1, min(args.max_results, 10)),
        include_answer=args.include_answer,
        search_depth=args.search_depth,
    )

    if args.format == "md":
        sys.stdout.write(to_markdown(res))
        return

    if args.format == "brave":
        res = to_brave_like(res)

    json.dump(res, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()

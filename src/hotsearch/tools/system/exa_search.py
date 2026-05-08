#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import pathlib
import re
import sys
import urllib.request
import urllib.error

from hotsearch import CACHE_SEARCH_DIR

EXA_URL = "https://api.exa.ai/search"


def _load_key(env_path: pathlib.Path, name: str = "EXA_API_KEY"):
    if not env_path.exists():
        return None
    try:
        txt = env_path.read_text(encoding="utf-8", errors="ignore")
        m = re.search(rf"^\s*{re.escape(name)}\s*=\s*(.+?)\s*$", txt, re.M)
        if m:
            v = m.group(1).strip().strip('"').strip("'")
            if v:
                return v
    except Exception:
        pass
    return None


def load_keys():
    keys = []
    k = os.environ.get("EXA_API_KEY")
    if k:
        keys.append(k.strip())
    k = _load_key(pathlib.Path.home() / ".env")
    if k and k not in keys:
        keys.append(k)
    return keys


def exa_search(query: str, num_results: int, search_type: str, text_max_chars: int, highlights: bool, key: str):
    payload = {
        "query": query,
        "numResults": num_results,
        "type": search_type,
    }
    contents = {}
    if text_max_chars:
        contents["text"] = {"maxCharacters": text_max_chars}
    if highlights:
        contents["highlights"] = {"maxCharacters": 4000}
    if contents:
        payload["contents"] = contents

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        EXA_URL,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-api-key": key,
            "User-Agent": "exa-search/1.0",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read().decode("utf-8", errors="replace")

    try:
        return json.loads(body)
    except json.JSONDecodeError:
        raise SystemExit(f"Exa returned non-JSON: {body[:300]}")


def search_all(query: str, num_results: int, search_type: str, text_max_chars: int, highlights: bool):
    keys = load_keys()
    if not keys:
        raise SystemExit("Missing EXA_API_KEY. Set env var or add to ~/.env")

    last_err = None
    for key in keys:
        try:
            return exa_search(query, num_results, search_type, text_max_chars, highlights, key)
        except urllib.error.HTTPError as e:
            last_err = e
            if 400 <= e.code < 500:
                continue
            raise

    raise SystemExit(f"All Exa API keys failed. Last error: {last_err}")


def to_brave_like(obj: dict) -> dict:
    results = []
    for r in (obj.get("results") or []):
        item = {
            "title": r.get("title"),
            "url": r.get("url"),
            "snippet": None,
        }
        text = r.get("text")
        if text:
            item["snippet"] = text[:500]
        elif r.get("highlights"):
            item["snippet"] = r["highlights"][0][:500]
        results.append(item)
    return {"query": obj.get("query"), "results": results}


def to_markdown(obj: dict) -> str:
    lines = []
    for i, r in enumerate((obj.get("results") or []), 1):
        title = (r.get("title") or "").strip() or r.get("url") or "(no title)"
        url = r.get("url") or ""
        lines.append(f"{i}. {title}")
        if url:
            lines.append(f"   {url}")
        text = r.get("text")
        if text:
            lines.append(f"   - {text[:300]}")
        elif r.get("highlights"):
            lines.append(f"   - {r['highlights'][0][:300]}")
    return "\n".join(lines).strip() + "\n"


def _save_search(query: str, data: dict):
    CACHE_SEARCH_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.md5(query.encode()).hexdigest()[:16]
    path = CACHE_SEARCH_DIR / f"exa_{key}.json"
    path.write_text(json.dumps({"query": query, "data": data, "source": "exa"}, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query", required=True)
    ap.add_argument("--num-results", type=int, default=5)
    ap.add_argument("--type", default="auto", choices=["auto", "fast", "instant", "deep-lite", "deep", "deep-reasoning"])
    ap.add_argument("--text-max-chars", type=int, default=0, help="Fetch full text up to N chars (0=off)")
    ap.add_argument("--highlights", action="store_true", help="Include highlight snippets")
    ap.add_argument("--format", default="raw", choices=["raw", "brave", "md"])
    ap.add_argument("--save", action="store_true", help="Save raw JSON to data/cache/search/")
    args = ap.parse_args()

    res = search_all(
        query=args.query,
        num_results=max(1, min(args.num_results, 20)),
        search_type=args.type,
        text_max_chars=args.text_max_chars,
        highlights=args.highlights,
    )

    if args.save:
        path = _save_search(args.query, res)
        sys.stderr.write(f"Saved to {path}\n")

    if args.format == "md":
        sys.stdout.write(to_markdown(res))
        return
    if args.format == "brave":
        res = to_brave_like(res)

    json.dump(res, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()

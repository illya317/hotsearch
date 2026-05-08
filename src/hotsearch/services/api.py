#!/usr/bin/env python3
"""
HTTP API gateway exposing all trends and feeds.
Runs on port 3000. Cache TTL is 24h, ?refresh=1 to force.
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from hotsearch import PROJECT_ROOT
from hotsearch import CACHE_API_DIR, CACHE_FEEDS_DIR

CACHE_API_DIR.mkdir(parents=True, exist_ok=True)

CACHE_TTL = 86400  # 24h
MEM_CACHE = {}


def _cache_path(key):
    return CACHE_API_DIR / f"{key.replace(':', '_')}.json"


def _read_cache(key):
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        entry = json.loads(path.read_text())
        if time.time() - entry.get("time", 0) > CACHE_TTL:
            path.unlink(missing_ok=True)
            return None
        return entry["data"]
    except Exception:
        return None


def _write_cache(key, data):
    path = _cache_path(key)
    path.write_text(json.dumps({"data": data, "time": time.time()}, ensure_ascii=False))


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise Exception(r.stderr.strip() or "command failed")
    return r.stdout.strip()


class APIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        refresh = params.get("refresh", [""])[0] in ("1", "true", "yes")

        try:
            if path == "/health":
                self._json({
                    "status": "ok",
                    "cache_files": len(list(CACHE_API_DIR.glob("*.json"))),
                })
                return

            result = self._dispatch(path, params, refresh)
            if result is not None:
                self._json({"data": result})
            else:
                self._json({"error": "not found", "endpoints": self._endpoints()}, 404)
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def _dispatch(self, path, params, refresh):
        # --- trends ---
        if path == "/hotsearch":
            platform = params.get("platform", ["hot"])[0]
            limit = params.get("limit", ["5"])[0]
            key = f"hotsearch:{platform}:{limit}"
            return self._cached(key, [
                "python3", "-m", "hotsearch.tools.trends.hotsearch",
                platform, limit,
            ], refresh)

        if path == "/ainews":
            source = params.get("source", ["all"])[0]
            limit = params.get("limit", ["5"])[0]
            key = f"ainews:{source}:{limit}"
            return self._cached(key, [
                "python3", "-m", "hotsearch.tools.trends.ainews",
                source, limit,
            ], refresh)

        if path == "/github-trending":
            limit = params.get("limit", ["10"])[0]
            key = f"github:{limit}"
            return self._cached(key, [
                "python3", "-m", "hotsearch.tools.trends.github_trending",
                limit,
            ], refresh)

        # --- feeds ---
        if path == "/videos":
            key = "videos"
            return self._cached(key, [
                "python3", "-m", "hotsearch.tools.feeds.video_feeds",
            ], refresh)

        if path == "/releases":
            key = "releases"
            return self._cached(key, [
                "python3", "-m", "hotsearch.tools.feeds.release_feeds",
            ], refresh)

        if path == "/laws":
            key = "laws"
            return self._cached(key, [
                "python3", "-m", "hotsearch.tools.feeds.newlaw", "--list",
            ], refresh)

        if path == "/laws/shanghai":
            key = "laws:shanghai"
            return self._cached(key, [
                "python3", "-m", "hotsearch.tools.feeds.newlaw_shanghai", "--list",
            ], refresh)

        # --- daily summary ---
        if path == "/daily":
            period = params.get("period", ["24h"])[0]
            return self._daily_summary(period)

        return None

    def _cached(self, key, cmd, refresh):
        now = time.time()
        if not refresh:
            # L1: memory
            if key in MEM_CACHE:
                entry = MEM_CACHE[key]
                if now - entry.get("time", 0) <= CACHE_TTL:
                    return entry["data"]
                del MEM_CACHE[key]
            # L2: file
            cached = _read_cache(key)
            if cached is not None:
                MEM_CACHE[key] = {"data": cached, "time": now}
                return cached
        # Miss or refresh: run
        result = _run(cmd)
        MEM_CACHE[key] = {"data": result, "time": now}
        _write_cache(key, result)
        return result

    def _daily_summary(self, period: str):
        """Read feeds state files and filter by period."""
        # Parse period
        if period.endswith("h"):
            hours = int(period[:-1])
        elif period.endswith("d"):
            hours = int(period[:-1]) * 24
        else:
            hours = 24
        threshold = datetime.now() - timedelta(hours=hours)

        def _is_recent(ts: float) -> bool:
            try:
                return ts >= threshold.timestamp()
            except Exception:
                return False

        result = {"period": period, "threshold": threshold.isoformat(), "feeds": {}}

        # Videos
        video_path = CACHE_FEEDS_DIR / "video_state.json"
        if video_path.exists():
            try:
                data = json.loads(video_path.read_text())
                recent = []
                for name, val in data.get("videos", {}).items():
                    if isinstance(val, dict) and _is_recent(val.get("timestamp", 0)):
                        recent.append({"name": name, "title": val.get("title"), "time": val.get("time"), "timestamp": val.get("timestamp")})
                result["feeds"]["videos"] = recent
            except Exception:
                result["feeds"]["videos"] = []

        # Releases
        release_path = CACHE_FEEDS_DIR / "release_state.json"
        if release_path.exists():
            try:
                data = json.loads(release_path.read_text())
                recent = []
                for name, val in data.get("releases", {}).items():
                    if isinstance(val, dict) and _is_recent(val.get("timestamp", 0)):
                        recent.append({"name": name, "title": val.get("title"), "time": val.get("time"), "timestamp": val.get("timestamp")})
                result["feeds"]["releases"] = recent
            except Exception:
                result["feeds"]["releases"] = []

        # Laws
        for key, filename in [("laws", "newlaw_last.json"), ("laws_shanghai", "newlaw_shanghai_last.json")]:
            law_path = CACHE_FEEDS_DIR / filename
            if law_path.exists():
                try:
                    data = json.loads(law_path.read_text())
                    if isinstance(data, dict):
                        ts = data.get("timestamp", 0)
                        if _is_recent(ts):
                            result["feeds"][key] = {
                                "time": data.get("time"),
                                "timestamp": ts,
                                "count": len(data.get("laws", [])),
                            }
                        else:
                            result["feeds"][key] = None
                    else:
                        result["feeds"][key] = None
                except Exception:
                    result["feeds"][key] = None
            else:
                result["feeds"][key] = None

        return result

    def _endpoints(self):
        return [
            "/hotsearch?platform=zhihu|weibo|eastmoney|ithome|xiaohongshu|bilibili|douban|hot&limit=5",
            "/ainews?source=all|decoder|hn|tc&limit=5",
            "/github-trending?limit=10",
            "/videos",
            "/releases",
            "/laws",
            "/laws/shanghai",
            "/daily?period=<N>h|<N>d",
            "/health",
        ]

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 3000), APIHandler)
    print("API running on port 3000 (24h cache TTL, ?refresh=1 to force)")
    server.serve_forever()

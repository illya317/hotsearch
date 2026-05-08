#!/usr/bin/env python3
"""
Lightweight HTTP API wrapping hotsearch, ainews, and github-trending.
Runs on port 3000. 5-minute cache.
"""

import json
import os
import subprocess
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from hotsearch import PROJECT_ROOT
from hotsearch.config import CACHE_DIR

CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL = 300  # 5 minutes

MEM_CACHE = {}


def _cache_path(key):
    return CACHE_DIR / f"{key.replace(':', '_')}.json"


def _read_cache(key):
    path = _cache_path(key)
    if not path.exists():
        return None
    try:
        entry = json.loads(path.read_text())
        if time.time() - entry["time"] < CACHE_TTL:
            return entry["data"]
    except Exception:
        pass
    return None


def _write_cache(key, data):
    path = _cache_path(key)
    path.write_text(json.dumps({"data": data, "time": time.time()}, ensure_ascii=False))


class APIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        try:
            if path == "/health":
                self._json({"status": "ok", "cache_files": len(list(CACHE_DIR.glob("*.json")))})
            elif path == "/hotsearch":
                platform = params.get("platform", ["hot"])[0]
                limit = params.get("limit", ["5"])[0]
                key = f"hotsearch:{platform}:{limit}"
                result = self._cached(key, ["python3", "-m", "hotsearch.tools.search.hotsearch", platform, limit])
                self._json({"data": result})
            elif path == "/ainews":
                source = params.get("source", ["all"])[0]
                limit = params.get("limit", ["5"])[0]
                key = f"ainews:{source}:{limit}"
                result = self._cached(key, ["python3", "-m", "hotsearch.tools.search.ainews", source, limit])
                self._json({"data": result})
            elif path == "/github-trending":
                limit = params.get("limit", ["10"])[0]
                key = f"github:{limit}"
                result = self._cached(key, ["python3", "-m", "hotsearch.tools.search.github_trending", limit])
                self._json({"data": result})
            else:
                self._json({"error": "not found", "endpoints": [
                    "/hotsearch?platform=eastmoney&limit=5",
                    "/ainews?source=all&limit=5",
                    "/github-trending?limit=10",
                    "/health",
                ]}, 404)
        except Exception as e:
            self._json({"error": str(e)}, 500)

    def _cached(self, key, cmd):
        now = time.time()
        # L1: memory
        if key in MEM_CACHE and now - MEM_CACHE[key]["time"] < CACHE_TTL:
            return MEM_CACHE[key]["data"]
        # L2: file
        cached = _read_cache(key)
        if cached is not None:
            MEM_CACHE[key] = {"data": cached, "time": now}
            return cached
        # Miss: run
        result = self._run(cmd)
        MEM_CACHE[key] = {"data": result, "time": now}
        _write_cache(key, result)
        return result

    def _run(self, cmd):
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            raise Exception(r.stderr.strip() or "command failed")
        return r.stdout.strip()

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 3000), APIHandler)
    print("API running on port 3000 (cache: 5min)")
    server.serve_forever()

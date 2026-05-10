#!/usr/bin/env python3
"""
新法速递推送脚本
- 从国家法律法规数据库 (flk.npc.gov.cn) 获取最新法律法规
- 对比上次记录，发现新法后通过飞书 Webhook 推送
- 用于 cron 定时调用
"""

import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
from hotsearch import CACHE_FEEDS_DIR  # noqa: E402

from .base import StandardItem, StandardResult, FeedAdapter  # noqa: E402

# --- 配置 ---
API_URL = "https://flk.npc.gov.cn/law-search/search/list"


class NewlawAdapter(FeedAdapter):
    name = "laws"
    tags = ["政策法规"]

    def normalize(self, raw: dict | list) -> StandardResult:
        assert isinstance(raw, dict)
        items: list[StandardItem] = []
        for item in raw.get("laws", []):
            status = "有效" if item.get("sxx") == 3 else "尚未生效"
            items.append(
                {
                    "id": str(item.get("bbbs", "")) if item.get("bbbs") else None,
                    "title": item.get("title", ""),
                    "url": None,
                    "time": item.get("gbrq", "") or item.get("sxrq", ""),
                    "tags": item.get("tags", []),
                    "summary": f"{item.get('flxz', '')} | {status}",
                    "source_name": item.get("flxz", ""),
                    "raw": item,
                }
            )
        return {
            "source_name": "法律法规",
            "items": items,
            "meta": {"count": raw.get("count")},
            "output": None,
        }

    def fetch(self, query: str = "", **kwargs) -> dict:
        laws = fetch_latest()
        return {"laws": laws, "count": len(laws)}

    def check_new(self) -> list[str]:
        return check_new_laws()


CACHE_FEEDS_DIR.mkdir(parents=True, exist_ok=True)
LAST_FILE = CACHE_FEEDS_DIR / "newlaw_last.json"
# 只关注中央法律法规（不含地方法规）
FLFG_CODES = [
    100,
    110,
    120,
    130,
    140,
    150,
    155,
    160,
    170,
    180,
    190,
    195,
    200,
    210,
    215,
    220,
    320,
    330,
    340,
    350,
]
PAGE_SIZE = 20


def _http_post(url, body):
    """发 POST 请求"""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception:
        # Fallback to curl (for local macOS SSL issues)
        result = subprocess.run(
            [
                "curl",
                "-sS",
                "--max-time",
                "15",
                "-X",
                "POST",
                url,
                "-H",
                "Content-Type: application/json",
                "-d",
                json.dumps(body),
            ],
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Request failed: {result.stderr.decode()}")
        return json.loads(result.stdout)


def fetch_latest():
    """获取最新法律法规列表"""
    data = _http_post(
        API_URL,
        {
            "page": 1,
            "size": PAGE_SIZE,
            "searchContent": "",
            "searchType": "1",
            "searchRange": "1",
            "sxx": [3, 4],
            "gbrq": [],
            "sxrq": [],
            "flfgCodeId": FLFG_CODES,
            "zdjgCodeId": [],
        },
    )

    laws = []
    for row in data.get("rows", []):
        laws.append(
            {
                "bbbs": row.get("bbbs"),
                "title": row.get("title"),
                "gbrq": row.get("gbrq"),
                "sxrq": row.get("sxrq"),
                "flxz": row.get("flxz"),
                "sxx": row.get("sxx"),
            }
        )
    return laws


def load_last():
    """加载上次记录"""
    if LAST_FILE.exists():
        data = json.loads(LAST_FILE.read_text(encoding="utf-8"))
        # Migrate old format (list) -> new format {"laws": [...], "updated_at": "..."}
        if isinstance(data, list):
            return {"laws": data, "updated_at": "1970-01-01T00:00:00"}
        return data
    return {"laws": [], "updated_at": "1970-01-01T00:00:00"}


def save_last(laws):
    """保存本次记录"""
    CACHE_FEEDS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    payload = {
        "laws": laws,
        "time": now.strftime("%Y-%m-%d %H:%M"),
        "timestamp": time.time(),
    }
    LAST_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def find_new(current, last):
    """找出新增的法律"""
    last_ids = {law["bbbs"] for law in last}
    return [law for law in current if law["bbbs"] not in last_ids]


def format_law(law):
    sxx = "🟢有效" if law["sxx"] == 3 else "🔵尚未生效"
    return (
        f"▸ 【{law['flxz']}】{law['title']}\n"
        f"  公布: {law['gbrq'] or '—'}  施行: {law['sxrq'] or '—'}  {sxx}"
    )


def check_new_laws() -> list[str]:
    """Check for new laws, update state, return formatted new items."""
    current = fetch_latest()
    if not current:
        return []

    last = load_last()
    if not last["laws"]:
        save_last(current)
        return []

    new_laws = find_new(current, last["laws"])
    if new_laws:
        save_last(current)
        today = datetime.now().strftime("%Y-%m-%d")
        lines = [f"📜 新法速递 ({today})\n"]
        for law in new_laws:
            lines.append(format_law(law))
            lines.append("")
        lines.append(f"共 {len(new_laws)} 条新法律法规")
        return ["\n".join(lines)]
    return []


def format_all(laws):
    """格式化全部法律列表"""
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f"📜 法律法规 ({today})\n"]
    for law in laws:
        lines.append(format_law(law))
        lines.append("")
    lines.append(f"共 {len(laws)} 条")
    return "\n".join(lines)


def format_message(new_laws):
    """格式化飞书消息"""
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f"📜 新法速递 ({today})\n"]
    for law in new_laws:
        lines.append(format_law(law))
        lines.append("")
    lines.append(f"共 {len(new_laws)} 条新法律法规")
    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="国家法律法规查询")
    parser.add_argument("--list", action="store_true", help="列出最新法律法规")
    args = parser.parse_args()

    current = fetch_latest()
    if not current:
        print("No data from API")
        return

    if args.list:
        print(format_all(current))
        return

    last = load_last()
    if not last:
        save_last(current)
        print(f"First run, saved baseline: {len(current)} laws")
        return

    new_laws = find_new(current, last)
    if new_laws:
        msg = format_message(new_laws)
        print(msg)
        save_last(current)
        print(f"\nFound {len(new_laws)} new laws")
    else:
        print("No new laws")
        save_last(current)


if __name__ == "__main__":
    main()

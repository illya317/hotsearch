#!/usr/bin/env python3
"""
上海新法速递推送脚本
- 从上海城市法规全书 (law.sfj.sh.gov.cn) 获取最新法规
- 对比上次记录，发现新法后通过飞书 App 推送
- 用于 cron 定时调用
"""

import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
from hotsearch.config import DATA_DIR

# --- 配置 ---
API_BASE = "https://law.sfj.sh.gov.cn/yidianApi/api/v1"
DATA_DIR = Path(os.environ.get("DATA_DIR", str(DATA_DIR)))
LAST_FILE = DATA_DIR / "newlaw_shanghai_last.json"

PAGE_SIZE = 50


def api_get(path, params=None):
    url = API_BASE + path
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception:
        result = subprocess.run(
            ["curl", "-sS", "--max-time", "15", url],
            capture_output=True,
        )
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)


def fetch_latest():
    """获取最新法规（第一页，按 implement_date 排序）"""
    data = api_get("/lawsearch", {"page": "1", "size": str(PAGE_SIZE)})
    if not data or data.get("code") != 200:
        return []

    laws = []
    for item in data.get("data", []):
        laws.append({
            "law_id": item.get("law_id"),
            "law_name": item.get("law_name"),
            "law_type": item.get("law_type"),
            "implement_date": item.get("implement_date"),
            "timeliness": item.get("timeliness"),
        })
    return laws


def load_last():
    if LAST_FILE.exists():
        return json.loads(LAST_FILE.read_text(encoding="utf-8"))
    return []


def save_last(laws):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LAST_FILE.write_text(json.dumps(laws, ensure_ascii=False, indent=2), encoding="utf-8")


def find_new(current, last):
    last_ids = {law["law_id"] for law in last}
    return [law for law in current if law["law_id"] not in last_ids]


def format_message(new_laws):
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f"📜 上海新法速递 ({today})\n"]
    for law in new_laws:
        timeliness = law.get("timeliness", "")
        lines.append(f"▸ 【{law['law_type']}】{law['law_name']}")
        lines.append(f"  施行: {law['implement_date'] or '—'}  {timeliness}")
        lines.append("")
    lines.append(f"共 {len(new_laws)} 条")
    lines.append("来源: law.sfj.sh.gov.cn")
    return "\n".join(lines)


def main():
    current = fetch_latest()
    if not current:
        print("No data from API")
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
        print(f"Found {len(new_laws)} new laws")
    else:
        print("No new Shanghai laws")
        save_last(current)


if __name__ == "__main__":
    main()

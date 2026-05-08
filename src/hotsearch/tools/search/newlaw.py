#!/usr/bin/env python3
"""
新法速递推送脚本
- 从国家法律法规数据库 (flk.npc.gov.cn) 获取最新法律法规
- 对比上次记录，发现新法后通过飞书 Webhook 推送
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
API_URL = "https://flk.npc.gov.cn/law-search/search/list"
DATA_DIR = Path(os.environ.get("DATA_DIR", str(DATA_DIR)))
LAST_FILE = DATA_DIR / "newlaw_last.json"
# 只关注中央法律法规（不含地方法规）
FLFG_CODES = [100, 110, 120, 130, 140, 150, 155, 160, 170, 180, 190, 195, 200, 210, 215, 220, 320, 330, 340, 350]
PAGE_SIZE = 20


def _http_post(url, body):
    """发 POST 请求"""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception:
        # Fallback to curl (for local macOS SSL issues)
        result = subprocess.run(
            ["curl", "-sS", "--max-time", "15", "-X", "POST", url,
             "-H", "Content-Type: application/json",
             "-d", json.dumps(body)],
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Request failed: {result.stderr.decode()}")
        return json.loads(result.stdout)


def fetch_latest():
    """获取最新法律法规列表"""
    data = _http_post(API_URL, {
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
    })

    laws = []
    for row in data.get("rows", []):
        laws.append({
            "bbbs": row.get("bbbs"),
            "title": row.get("title"),
            "gbrq": row.get("gbrq"),
            "sxrq": row.get("sxrq"),
            "flxz": row.get("flxz"),
            "sxx": row.get("sxx"),
        })
    return laws


def load_last():
    """加载上次记录"""
    if LAST_FILE.exists():
        return json.loads(LAST_FILE.read_text(encoding="utf-8"))
    return []


def save_last(laws):
    """保存本次记录"""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LAST_FILE.write_text(json.dumps(laws, ensure_ascii=False, indent=2), encoding="utf-8")


def find_new(current, last):
    """找出新增的法律"""
    last_ids = {law["bbbs"] for law in last}
    return [law for law in current if law["bbbs"] not in last_ids]


def format_message(new_laws):
    """格式化飞书消息"""
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f"📜 新法速递 ({today})\n"]
    for law in new_laws:
        sxx = "🟢有效" if law["sxx"] == 3 else "🔵尚未生效"
        lines.append(f"▸ 【{law['flxz']}】{law['title']}")
        lines.append(f"  公布: {law['gbrq'] or '—'}  施行: {law['sxrq'] or '—'}  {sxx}")
        lines.append("")
    lines.append(f"共 {len(new_laws)} 条新法律法规")
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
        print(f"\nFound {len(new_laws)} new laws")
    else:
        print("No new laws")
        save_last(current)


if __name__ == "__main__":
    main()

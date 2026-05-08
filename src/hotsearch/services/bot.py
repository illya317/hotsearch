#!/usr/bin/env python3
"""
Feishu WebSocket interactive bot.
No public URL needed - connects outbound to Feishu.
"""

import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

from hotsearch import PROJECT_ROOT

import lark_oapi as lark
from hotsearch.tools.search.video_feeds import get_videos

FS_APP_ID = os.environ.get("FS_ANYA", "")
FS_APP_SECRET = os.environ.get("FS_ANYAS", "")

# --- Commands ---
_COMMANDS_RAW = {
    "hot": "hot", "热搜": "hot", "热点": "hot",
    "fi": "eastmoney", "财经": "eastmoney", "东方财富": "eastmoney",
    "it": "ithome",
    "ai": "ainews", "AI新闻": "ainews",
    "gh": "github",
    "search": "search", "搜索": "search",
    "xhs": "xiaohongshu", "小红书": "xiaohongshu",
    "mv": "douban", "豆瓣": "douban", "电影": "douban",
    "视频": "videos", "vd": "videos", "VD": "videos",
    "知乎": "zhihu", "微博": "weibo",
    "push": "push",
    "帮助": "help", "help": "help",
}
COMMANDS = {}
for k, v in _COMMANDS_RAW.items():
    COMMANDS[k] = v
    COMMANDS[k.lower()] = v
    COMMANDS[k.upper()] = v
    COMMANDS[k.capitalize()] = v

STATE_FILE = str(PROJECT_ROOT / "data" / "cache" / "state.json")
NEWLAW_FILE = str(PROJECT_ROOT / "data" / "cache" / "newlaw_last.json")
NEWLAW_SH_FILE = str(PROJECT_ROOT / "data" / "cache" / "newlaw_shanghai_last.json")

TOOL_PREFIX = "hotsearch.tools.search"
TOOL_SYS_PREFIX = "hotsearch.tools.system"


def _run_tool(*args) -> str:
    r = subprocess.run(args, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        return f"Error: {r.stderr.strip()}"
    return r.stdout.strip()


def strip_links(text):
    lines = text.split("\n")
    return "\n".join(l for l in lines if not re.match(r"^\s*https?://\S+\s*$", l.strip()))


def load_state():
    try:
        return json.loads(open(STATE_FILE).read())
    except Exception:
        return {"videos": {}, "releases": {}}


def load_newlaw_state(filepath):
    try:
        return json.loads(open(filepath).read())
    except Exception:
        return None


def get_push_status():
    state = load_state()
    lines = ["📊 追踪状态概览\n"]

    lines.append("📺 视频频道 (6个)")
    videos_state = state.get("videos", {})
    from hotsearch.tools.search.video_feeds import VIDEO_FEEDS, fetch_url, parse_latest_item
    for name, url in VIDEO_FEEDS:
        check_url = url.replace("limit=3", "limit=1")
        data = fetch_url(check_url)
        stored_title = videos_state.get(name, "")
        if data.startswith("Error"):
            current_title = "(获取失败)"
            status = "❌"
        else:
            item = parse_latest_item(data)
            if item:
                current_title = item["title"]
                status = "✅已最新" if current_title == stored_title else "🆕有更新"
            else:
                current_title = "(解析失败)"
                status = "❌"
        display = f"• {name}: {current_title[:40]}{'...' if len(current_title) > 40 else ''} [{status}]"
        lines.append(display)

    lines.append("\n\n📦 软件仓库 (2个)")
    from hotsearch.tools.search.release_feeds import RELEASE_FEEDS, get_latest_release
    releases_state = state.get("releases", {})
    for name, url in RELEASE_FEEDS.items():
        release = get_latest_release(url)
        stored_title = releases_state.get(name, "")
        if release:
            current_title = release["title"]
            status = "✅已最新" if current_title == stored_title else "🆕有更新"
            display = f"• {name}: {current_title[:40]}{'...' if len(current_title) > 40 else ''} [{status}]"
        else:
            display = f"• {name}: (获取失败) [❌]"
        lines.append(display)

    lines.append("\n\n📋 法规监控 (2个)")
    newlaw_state = load_newlaw_state(NEWLAW_FILE)
    if newlaw_state and newlaw_state.get("title"):
        law_title = newlaw_state["title"]
        lines.append(f"• 国家法律法规: {law_title[:40]}{'...' if len(law_title) > 40 else ''}")
    else:
        lines.append("• 国家法律法规: (无记录)")

    newlaw_sh_state = load_newlaw_state(NEWLAW_SH_FILE)
    if newlaw_sh_state and newlaw_sh_state.get("title"):
        law_title = newlaw_sh_state["title"]
        lines.append(f"• 上海地方法规: {law_title[:40]}{'...' if len(law_title) > 40 else ''}")
    else:
        lines.append("• 上海地方法规: (无记录)")

    lines.append("\n💡 提示: 有新内容时会自动推送")
    return "\n".join(lines)


# Command → (tool_path, platform, limit) or special handler
HOTSEARCH_CMDS = {
    "zhihu":       ("hotsearch", "zhihu", 5),
    "weibo":       ("hotsearch", "weibo", 5),
    "xiaohongshu": ("hotsearch", "xiaohongshu", 5),
    "ithome":      ("hotsearch", "ithome", 5),
    "douban":      ("hotsearch", "douban", 5),
    "eastmoney":   ("hotsearch", "eastmoney", 5),
    "ainews":      ("ainews", "decoder", 5),
    "github":      ("github_trending", None, 5),
}


def get_help():
    return """🤖 Anya 支持的命令:

hot — 知乎+微博热搜
fi — 东方财富热榜
it — IT之家
ai — AI新闻 (THE DECODER)
gh — GitHub热门
xhs — 小红书
mv — 豆瓣电影
vd — Bilibili视频
push — 追踪状态概览
help — 本菜单

💡 提示: 可在命令后加数字指定条数，如 "fi 10" """


def handle_message(text):
    text = text.strip()
    parts = text.split()
    base_cmd = parts[0] if parts else ""
    try:
        limit = int(parts[1]) if len(parts) > 1 else 5
        limit = max(1, min(10, limit))
    except ValueError:
        limit = 5

    cmd = COMMANDS.get(base_cmd)

    if cmd == "help":
        return get_help()
    elif cmd == "videos":
        return get_videos()
    elif cmd == "push":
        return get_push_status()
    elif cmd == "hot":
        r1 = _run_tool("python3", "-m", f"{TOOL_PREFIX}.hotsearch", "zhihu", str(limit))
        r2 = _run_tool("python3", "-m", f"{TOOL_PREFIX}.hotsearch", "weibo", str(limit))
        return f"{r1}\n\n{r2}"
    elif cmd in HOTSEARCH_CMDS:
        tool, platform, _ = HOTSEARCH_CMDS[cmd]
        args = ["python3", "-m", f"{TOOL_PREFIX}.{tool}"]
        if platform:
            args.append(platform)
        args.append(str(limit))
        return _run_tool(*args)
    elif cmd == "search":
        query = " ".join(parts[1:]) if len(parts) > 1 else ""
        if not query:
            return "请输入搜索内容，例如: search 什么是量子计算"
        return _run_tool("python3", "-m", f"{TOOL_SYS_PREFIX}.tavily_search",
                         "--query", query, "--max-results", str(limit), "--format", "md")
    else:
        return "未知命令，输入 help 查看可用命令"


# --- Feishu WebSocket ---

_processed_msgs = set()
_client = None


def get_client():
    global _client
    if _client is None:
        _client = lark.Client.builder().app_id(FS_APP_ID).app_secret(FS_APP_SECRET).build()
    return _client


def reply_async(message_id, text, chat_id=None):
    try:
        reply = handle_message(text)
        if len(reply) > 4000:
            reply = reply[:3950] + "\n\n... (截断)"

        content_json = json.dumps({"text": reply}, ensure_ascii=False)
        req = lark.im.v1.ReplyMessageRequest.builder() \
            .message_id(message_id) \
            .request_body(lark.im.v1.ReplyMessageRequestBody.builder()
                .content(content_json)
                .msg_type("text")
                .build()) \
            .build()
        get_client().im.v1.message.reply(req)
    except Exception as e:
        print(f"Reply error: {e}")


def do_p2_im_message_receive_v1(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
    msg = data.event.message
    if msg.message_type != "text":
        return

    if msg.message_id in _processed_msgs:
        return
    _processed_msgs.add(msg.message_id)
    if len(_processed_msgs) > 500:
        _processed_msgs.clear()

    content = json.loads(msg.content)
    text = content.get("text", "").strip()
    text = re.sub(r"@_\w+\s*", "", text).strip()
    mentions = data.event.message.mentions if hasattr(data.event.message, 'mentions') and data.event.message.mentions else []
    for m in mentions:
        if hasattr(m, 'key') and m.key:
            text = text.replace(m.key, "").strip()
    print(f"[MSG] raw={content}, cleaned='{text}'", flush=True)
    if not text:
        return

    chat_id = msg.chat_id if hasattr(msg, 'chat_id') else None
    threading.Thread(target=reply_async, args=(msg.message_id, text, chat_id), daemon=True).start()


def main():
    event_handler = lark.EventDispatcherHandler.builder("", "") \
        .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1) \
        .build()

    cli = lark.ws.Client(
        FS_APP_ID,
        FS_APP_SECRET,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO,
    )
    cli.start()


if __name__ == "__main__":
    main()

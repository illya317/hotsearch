#!/usr/bin/env python3
"""
Feishu WebSocket interactive bot.
No public URL needed - connects outbound to Feishu.
"""

import json
import os
import re
import subprocess
import threading

import lark_oapi as lark

from hotsearch import BOT_CONFIG, CACHE_FEEDS_DIR
from hotsearch.tools.feeds.video_feeds import get_videos  # type: ignore

FS_APP_ID = os.environ.get("FS_APP_ID", "")
FS_APP_SECRET = os.environ.get("FS_APP_SECRET", "")

# --- Load config ---
_bot_cfg = json.loads(BOT_CONFIG.read_text())

# Build case-insensitive commands map: alias -> cmd_id
COMMANDS = {}
for cmd_id, cfg in _bot_cfg.items():
    for alias in cfg.get("aliases", []):
        COMMANDS[alias] = cmd_id
        COMMANDS[alias.lower()] = cmd_id
        COMMANDS[alias.upper()] = cmd_id
        COMMANDS[alias.capitalize()] = cmd_id

TOOL_PREFIX = "hotsearch.tools"


def _run_tool(*args) -> str:
    r = subprocess.run(args, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        return f"Error: {r.stderr.strip()}"
    return r.stdout.strip()


def _run_hotsearch(cmd_id: str, limit: int) -> str:
    cfg = _bot_cfg.get(cmd_id, {})
    tool = cfg.get("tool")
    platform = cfg.get("platform")
    args = ["python3", "-m", f"{TOOL_PREFIX}.{tool}"]
    if platform:
        args.append(platform)
    args.append(str(limit))
    args.append("--json")
    raw = _run_tool(*args)
    # Parse JSON and format via schemas
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if tool == "trends.hotsearch":
        from hotsearch.schemas import HotsearchData

        return HotsearchData.from_dict(data).format_text()
    elif tool == "trends.ainews":
        from hotsearch.schemas import AINewsData

        return AINewsData.from_dict(data).format_text()
    elif tool == "trends.github_trending":
        from hotsearch.schemas import GitHubTrendingData

        return GitHubTrendingData.from_dict(data).format_text()
    return raw


def strip_links(text):
    lines = text.split("\n")
    return "\n".join(
        line for line in lines if not re.match(r"^\s*https?://\S+\s*$", line.strip())
    )


def get_push_status():
    lines = ["📊 追踪状态概览\n"]

    from hotsearch.tools.feeds import get_tools

    for tool in get_tools():
        if not tool.state_file:
            continue
        items = tool.get_status()
        if not items:
            continue
        lines.append(f"\n{tool.display_name or tool.name} ({len(items)}个)")
        for item in items:
            name = item.get("name", "")
            title = item.get("title", "")
            status = item.get("status", "")
            lines.append(f"• {name}: {title} [{status}]")

    lines.append("\n💡 提示: 有新内容时会自动推送")
    return "\n".join(lines)


def get_help():
    lines = ["🤖 Anya 支持的命令:\n"]
    for cmd_id, cfg in _bot_cfg.items():
        help_text = cfg.get("help", "")
        aliases = cfg.get("aliases", [])
        primary = aliases[0] if aliases else cmd_id
        lines.append(f"{primary} — {help_text}")
    lines.append("")
    lines.append('💡 提示: 可在命令后加数字指定条数，如 "fi 10"')
    return "\n".join(lines)


def handle_message(text):
    text = text.strip()
    parts = text.split()
    base_cmd = parts[0] if parts else ""
    try:
        limit = int(parts[1]) if len(parts) > 1 else 5
        limit = max(1, min(10, limit))
    except ValueError:
        limit = 5

    cmd_id = COMMANDS.get(base_cmd)
    if not cmd_id:
        return "未知命令，输入 help 查看可用命令"

    cfg = _bot_cfg.get(cmd_id, {})
    cmd_type = cfg.get("type")

    if cmd_type == "help":
        return get_help()
    elif cmd_type == "videos":
        return get_videos()
    elif cmd_type == "push":
        return get_push_status()
    elif cmd_type == "group":
        results = []
        for target_id in cfg.get("targets", []):
            target_cfg = _bot_cfg.get(target_id, {})
            if "tool" in target_cfg:
                results.append(_run_hotsearch(target_id, limit))
        return "\n\n".join(results)
    elif "tool" in cfg:
        return _run_hotsearch(cmd_id, limit)
    else:
        return "未知命令，输入 help 查看可用命令"


# --- Feishu WebSocket ---

_processed_msgs = set()
_client = None


def get_client() -> lark.Client:
    global _client
    if _client is None:
        _client = (
            lark.Client.builder().app_id(FS_APP_ID).app_secret(FS_APP_SECRET).build()
        )
    return _client


def reply_async(message_id, text, chat_id=None):
    try:
        reply = handle_message(text)
        if len(reply) > 4000:
            reply = reply[:3950] + "\n\n... (截断)"

        content_json = json.dumps({"text": reply}, ensure_ascii=False)
        req = (
            lark.im.v1.ReplyMessageRequest.builder()
            .message_id(message_id)
            .request_body(
                lark.im.v1.ReplyMessageRequestBody.builder()
                .content(content_json)
                .msg_type("text")
                .build()
            )
            .build()
        )
        client = get_client()
        im = client.im
        assert im is not None
        v1 = im.v1
        assert v1 is not None
        message = v1.message
        assert message is not None
        message.reply(req)
    except Exception as e:
        print(f"Reply error: {e}")


def do_p2_im_message_receive_v1(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
    event = data.event
    assert event is not None
    msg = event.message
    assert msg is not None
    if msg.message_type != "text":
        return

    message_id = msg.message_id
    assert message_id is not None
    if message_id in _processed_msgs:
        return
    _processed_msgs.add(message_id)
    if len(_processed_msgs) > 500:
        _processed_msgs.clear()

    msg_content = msg.content
    assert msg_content is not None
    content = json.loads(msg_content)
    text = content.get("text", "").strip()
    text = re.sub(r"@_\w+\s*", "", text).strip()
    mentions = msg.mentions if hasattr(msg, "mentions") and msg.mentions else []
    for m in mentions:
        if hasattr(m, "key") and m.key:
            text = text.replace(m.key, "").strip()
    print(f"[MSG] raw={content}, cleaned='{text}'", flush=True)
    if not text:
        return

    chat_id = msg.chat_id if hasattr(msg, "chat_id") else None
    threading.Thread(
        target=reply_async, args=(message_id, text, chat_id), daemon=True
    ).start()


def main():
    event_handler = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(do_p2_im_message_receive_v1)
        .build()
    )

    cli = lark.ws.Client(
        FS_APP_ID,
        FS_APP_SECRET,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO,
    )
    cli.start()


if __name__ == "__main__":
    main()

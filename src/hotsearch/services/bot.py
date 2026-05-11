#!/usr/bin/env python3
"""
Feishu WebSocket interactive bot.
No public URL needed - connects outbound to Feishu.
"""

import json
import os
import re
import threading

import lark_oapi as lark

from hotsearch import BOT_CONFIG, CONFIG_DIR

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


def _standard_to_hotsearch(normalized: dict, platform: str) -> dict:
    """Convert StandardResult to HotsearchData dict."""
    return {
        "platforms": [
            {
                "platform": platform,
                "display_name": normalized.get("source_name", ""),
                "items": [
                    {
                        "title": i.get("title", ""),
                        "heat_str": i.get("summary", ""),
                        "heat_num": 0,
                        "label_name": "",
                        "rating": None,
                        "item_key": "",
                    }
                    for i in normalized.get("items", [])
                ],
            }
        ]
    }


def _standard_to_ainews(normalized: dict, source: str) -> dict:
    """Convert StandardResult to AINewsData dict."""
    return {
        "sources": [
            {
                "source": source,
                "display_name": normalized.get("source_name", ""),
                "items": [
                    {
                        "title": i.get("title", ""),
                        "link": i.get("url", ""),
                        "date": i.get("time", ""),
                        "desc": i.get("summary", ""),
                    }
                    for i in normalized.get("items", [])
                ],
            }
        ]
    }


def _standard_to_github(normalized: dict) -> dict:
    """Convert StandardResult to GitHubTrendingData dict."""
    return {
        "items": [
            {
                "name": i.get("title", ""),
                "stars": i.get("raw", {}).get("stars", 0),
                "desc": i.get("summary", ""),
                "lang": i.get("raw", {}).get("lang", ""),
            }
            for i in normalized.get("items", [])
        ]
    }


def _render_feeds(normalized: dict) -> str:
    """Render feeds StandardResult via feeds_summary.j2 template."""
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(CONFIG_DIR / "prompts"))
    template = env.get_template("feeds_summary.j2")
    groups = {normalized.get("source_name", ""): normalized.get("items", [])}
    return template.render(groups=groups, total=len(normalized.get("items", [])))


def _run_trends(cmd_id: str, limit: int) -> str:
    """Fetch trends via adapter and format via schemas."""
    cfg = _bot_cfg.get(cmd_id, {})
    tool_name = cfg.get("tool", "").replace("trends.", "")
    platform = cfg.get("platform")

    from hotsearch.tools.trends import get_tool

    adapter = get_tool(tool_name)
    if not adapter:
        return f"未找到适配器: {tool_name}"

    kwargs = {"limit": limit}
    if platform:
        kwargs["platform"] = platform

    raw = adapter.fetch(**kwargs)
    normalized = adapter.normalize(raw)
    from hotsearch.tools.base import validate_standard_result

    validate_standard_result(normalized)

    if tool_name == "hotsearch":
        from hotsearch.schemas import HotsearchData
        return HotsearchData.from_dict(_standard_to_hotsearch(normalized, platform or "hot")).format_text()
    elif tool_name == "ainews":
        from hotsearch.schemas import AINewsData
        return AINewsData.from_dict(_standard_to_ainews(normalized, platform or "decoder")).format_text()
    elif tool_name == "github_trending":
        from hotsearch.schemas import GitHubTrendingData
        return GitHubTrendingData.from_dict(_standard_to_github(normalized)).format_text()

    return str(normalized)


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
        from hotsearch.tools.feeds import get_tool
        adapter = get_tool("videos")
        if not adapter:
            return "未找到视频适配器"
        raw = adapter.fetch()
        normalized = adapter.normalize(raw)
        from hotsearch.tools.base import validate_standard_result

        validate_standard_result(normalized)
        return _render_feeds(normalized)
    elif cmd_type == "push":
        return get_push_status()
    elif cmd_type == "group":
        results = []
        for target_id in cfg.get("targets", []):
            target_cfg = _bot_cfg.get(target_id, {})
            if "tool" in target_cfg:
                results.append(_run_trends(target_id, limit))
        return "\n\n".join(results)
    elif "tool" in cfg:
        tool = cfg.get("tool", "")
        if tool.startswith("trends."):
            return _run_trends(cmd_id, limit)
        elif tool.startswith("feeds."):
            from hotsearch.tools.feeds import get_tool
            adapter = get_tool(tool.replace("feeds.", ""))
            if not adapter:
                return f"未找到适配器: {tool}"
            raw = adapter.fetch(limit=limit)
            normalized = adapter.normalize(raw)
            from hotsearch.tools.base import validate_standard_result

            validate_standard_result(normalized)
            return _render_feeds(normalized)
        return _run_trends(cmd_id, limit)
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

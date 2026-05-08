#!/usr/bin/env python3
"""Shared Feishu message sending utilities. Imported by tools and services."""

import json
import os
import sys
import time
import urllib.error
import urllib.request


def get_credentials(agent: str | None = None) -> tuple[str | None, str | None]:
    if agent:
        name = agent.upper()
        app_id = os.getenv(f"FS_{name}")
        app_secret = os.getenv(f"FS_{name}S")
        if app_id and app_secret:
            return app_id, app_secret
    return os.getenv("FEISHU_APP_ID"), os.getenv("FEISHU_APP_SECRET")


def get_receiver(agent: str | None = None) -> str | None:
    if agent:
        val = os.getenv(f"FS_KOITO_{agent.upper()}")
        if val:
            return val
    return os.getenv("FEISHU_RECEIVER_ID")


def get_token(app_id: str, app_secret: str) -> str | None:
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    data = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read()).get("tenant_access_token")


def send_text(token: str, receiver: str, text: str) -> bool:
    receive_id_type = "chat_id" if receiver.startswith("oc_") else "open_id"
    url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_id_type}"
    content = json.dumps({"text": text})
    payload = {"receive_id": receiver, "msg_type": "text", "content": content}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json",
    }, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())
        if result.get("code") == 0:
            return True
        print(f"飞书发送失败: {result.get('msg')}", file=sys.stderr)
        return False


def send_message(token: str, receiver: str, msg_type: str, content: str) -> str | None:
    """Send arbitrary message type, returns message_id on success."""
    if receiver.startswith("oc_"):
        receive_id_type = "chat_id"
    else:
        receive_id_type = "open_id"
    url = f"https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type={receive_id_type}"
    payload = {"receive_id": receiver, "msg_type": msg_type, "content": content}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json",
    }, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            if result.get("code") == 0:
                return result.get("data", {}).get("message_id")
            print(f"Send error: {result.get('msg')}", file=sys.stderr)
            return None
    except urllib.error.HTTPError as e:
        print(f"Send HTTP error: {e.code} - {e.read().decode()}", file=sys.stderr)
        return None


def send_to_feishu(text: str, agent: str | None = None, max_retry: int = 5):
    """High-level: get token, send text, with retry."""
    app_id, app_secret = get_credentials(agent)
    if not app_id or not app_secret:
        print("错误: 飞书凭证未配置", file=sys.stderr)
        sys.exit(1)

    receiver = get_receiver(agent)
    if not receiver:
        print("错误: 飞书接收人未配置", file=sys.stderr)
        sys.exit(1)

    for attempt in range(1, max_retry + 1):
        try:
            token = get_token(app_id, app_secret)
            if not token:
                raise Exception("获取 token 失败")
            if send_text(token, receiver, text):
                print(f"飞书发送成功 (第 {attempt} 次)")
                return
            raise Exception("发送返回失败")
        except Exception as e:
            print(f"第 {attempt}/{max_retry} 次失败: {e}", file=sys.stderr)
            if attempt < max_retry:
                print("等待 60 秒后重试...", file=sys.stderr)
                time.sleep(60)

    print("飞书发送失败，已达最大重试次数", file=sys.stderr)
    sys.exit(1)

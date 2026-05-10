#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "websockets>=10.0",
# ]
# ///
"""
Send voice messages to Feishu: Text → Minimax TTS → OPUS → Feishu.

Usage:
    uv run send.py --text "你好"
    uv run send.py --text "你好" --voice "female-tianmei" --speed 1.2
    uv run send.py --text "你好" --receiver ou_xxxxx
"""

import argparse
import asyncio
import json
import os
import ssl
import subprocess
import sys
import urllib.request
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))
from hotsearch import VOICES_CONFIG  # noqa: E402
from hotsearch.tools.system.feishu_send import (  # noqa: E402
    get_credentials,
    get_receiver,
    get_token,
    send_message,
)

DEFAULT_VOICE = "female-shaonv"


def load_agent_voices(lang: str | None = None) -> dict:
    if VOICES_CONFIG.exists():
        try:
            data = json.loads(VOICES_CONFIG.read_text())
            key = f"voice_id_{lang}" if lang else "voice_id"
            result = {}
            for k, v in data.items():
                if isinstance(v, dict):
                    result[k] = v.get(key) or v.get("voice_id", DEFAULT_VOICE)
                else:
                    result[k] = v
            return result
        except Exception:
            pass
    return {}


PROXY_KEYS = [
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "SOCKS_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "socks_proxy",
]


def detect_agent() -> str | None:
    """从工作目录推断 agent 名字，如 workspace-illya → illya"""
    cwd = Path.cwd().name
    if cwd.startswith("workspace-"):
        return cwd.removeprefix("workspace-")
    return None


def resolve_agent(explicit: str | None) -> str | None:
    return explicit or detect_agent()


def resolve_voice(
    explicit_voice: str | None, agent: str | None = None, lang: str | None = None
) -> str:
    if explicit_voice:
        return explicit_voice
    if agent:
        return load_agent_voices(lang).get(agent.lower(), DEFAULT_VOICE)
    return DEFAULT_VOICE


# --- Feishu auth & send ---


def _load_config() -> dict:
    config_path = Path("~/.openclaw/config/feishu.json").expanduser()
    if config_path.exists():
        try:
            return json.loads(config_path.read_text())
        except Exception:
            pass
    return {}


def _get_credentials_with_config(
    agent: str | None = None,
) -> tuple[str | None, str | None]:
    """Extended credential lookup that also checks ~/.openclaw/config/feishu.json."""
    app_id, app_secret = get_credentials(agent)
    if app_id and app_secret:
        return app_id, app_secret
    config = _load_config()
    return (
        config.get("appId") or config.get("app_id"),
        config.get("appSecret") or config.get("app_secret"),
    )


def _get_receiver_with_config(
    explicit: str | None, agent: str | None = None
) -> str | None:
    """Extended receiver lookup that also checks config file."""
    if explicit:
        return explicit
    result = get_receiver(agent)
    if result:
        return result
    config = _load_config()
    return config.get("receiver_id") or None


def get_duration_ms(audio_path: Path) -> int:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(float(result.stdout.strip()) * 1000)
    except Exception:
        pass
    return 3000


def upload_audio(token: str, file_path: Path) -> str | None:
    duration_ms = get_duration_ms(file_path)
    boundary = "----FormBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file_type"\r\n\r\nopus\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file_name"\r\n\r\nvoice.opus\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="duration"\r\n\r\n{duration_ms}\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode()
    body += file_path.read_bytes()
    body += f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/im/v1/files",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read()).get("data", {}).get("file_key")
    except Exception as e:
        print(f"Upload error: {e}", file=sys.stderr)
        return None


# --- TTS ---


async def minimax_tts(
    text: str,
    output_path: Path,
    api_key: str,
    voice_id: str,
    model: str = "speech-2.8-hd",
    speed: float = 1.0,
) -> bool:
    """Text → Minimax WebSocket TTS → MP3 temp file."""
    import websockets

    # Temporarily clear proxy env vars so websockets doesn't pick them up
    saved_proxy = {k: os.environ.pop(k) for k in PROXY_KEYS if k in os.environ}

    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        async with websockets.connect(
            "wss://api.minimaxi.com/ws/v1/t2a_v2",
            additional_headers=headers,
            ssl=ssl_context,
            proxy=None,
        ) as ws:
            connected = json.loads(await ws.recv())
            if connected.get("event") != "connected_success":
                print(f"TTS connection failed: {connected}", file=sys.stderr)
                return False

            await ws.send(
                json.dumps(
                    {
                        "event": "task_start",
                        "model": model,
                        "voice_setting": {
                            "voice_id": voice_id,
                            "speed": speed,
                            "vol": 1,
                            "pitch": 0,
                            "english_normalization": False,
                        },
                        "audio_setting": {
                            "sample_rate": 24000,
                            "bitrate": 128000,
                            "format": "mp3",
                            "channel": 1,
                        },
                    }
                )
            )

            resp = json.loads(await ws.recv())
            if resp.get("event") != "task_started":
                print(f"TTS task start failed: {resp}", file=sys.stderr)
                return False

            await ws.send(json.dumps({"event": "task_continue", "text": text}))

            audio_data = b""
            while True:
                resp = json.loads(await ws.recv())
                if "base_resp" in resp and resp["base_resp"].get("status_code") != 0:
                    print(
                        f"TTS error: {resp['base_resp'].get('status_msg')}",
                        file=sys.stderr,
                    )
                    return False
                if "data" in resp and "audio" in resp["data"]:
                    audio_hex = resp["data"]["audio"]
                    if audio_hex:
                        audio_data += bytes.fromhex(audio_hex)
                if resp.get("is_final"):
                    break

            await ws.send(json.dumps({"event": "task_finish"}))

            if audio_data:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(audio_data)
                print(f"TTS done: {len(audio_data)} bytes")
                return True
            else:
                print("TTS: no audio data received", file=sys.stderr)
                return False

    except Exception as e:
        print(f"TTS error: {e}", file=sys.stderr)
        return False
    finally:
        os.environ.update(saved_proxy)


def convert_to_opus(input_path: Path, opus_path: Path) -> bool:
    """Any audio → OPUS 16kHz mono via FFmpeg."""
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-acodec",
            "libopus",
            "-ac",
            "1",
            "-ar",
            "16000",
            str(opus_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"FFmpeg error: {result.stderr}", file=sys.stderr)
        return False
    print(f"Converted to OPUS: {opus_path.stat().st_size} bytes")
    return True


# --- Main ---


def main():
    parser = argparse.ArgumentParser(description="Send voice message to Feishu via TTS")
    parser.add_argument("--text", "-t", required=True, help="Text to speak")
    parser.add_argument(
        "--voice", "-v", default=None, help="Voice ID (overrides agent voice)"
    )
    parser.add_argument(
        "--agent", "-a", default=None, help="Agent name (e.g. illya, kuro)"
    )
    parser.add_argument(
        "--speed", "-s", type=float, default=1.0, help="Speed (0.5-2.0)"
    )
    parser.add_argument(
        "--lang",
        "-l",
        default=None,
        help="Language for voice selection (e.g. ja for Japanese)",
    )
    parser.add_argument("--receiver", "-r", help="Receiver open_id")
    parser.add_argument("--chat-id", help="Group chat_id (send to group instead of DM)")
    args = parser.parse_args()

    # Agent (--agent 优先，否则从工作目录推断)
    agent = resolve_agent(args.agent)

    # Voice
    voice = resolve_voice(args.voice, agent, args.lang)

    # Receiver: --chat-id (群聊) 优先，否则 --receiver / env (私聊)
    receiver = args.chat_id or _get_receiver_with_config(args.receiver, agent)
    if not receiver:
        print(
            "Error: No receiver. Use --chat-id, --receiver, --agent, or set FEISHU_RECEIVER_ID",
            file=sys.stderr,
        )
        sys.exit(1)

    # Feishu credentials
    app_id, app_secret = _get_credentials_with_config(agent)
    if not app_id or not app_secret:
        print(
            "Error: No Feishu credentials. Set FEISHU_APP_ID/FEISHU_APP_SECRET",
            file=sys.stderr,
        )
        sys.exit(1)

    # Minimax API key
    api_key = os.getenv("MINIMAX_API_KEY")
    if not api_key:
        print("Error: MINIMAX_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    tmp_mp3 = Path("/tmp/feishu_voice_tmp.mp3")
    tmp_opus = Path("/tmp/feishu_voice.opus")

    # Step 1: TTS
    print(f"[1/4] TTS (voice: {voice}, speed: {args.speed}x) ...")
    if not asyncio.run(
        minimax_tts(args.text, tmp_mp3, api_key, voice_id=voice, speed=args.speed)
    ):
        sys.exit(1)

    # Step 2: Convert to OPUS
    print("[2/4] FFmpeg → OPUS 16kHz mono ...")
    if not convert_to_opus(tmp_mp3, tmp_opus):
        sys.exit(1)
    tmp_mp3.unlink(missing_ok=True)

    # Step 3: Get token & upload
    print("[3/4] Uploading to Feishu ...")
    token = get_token(app_id, app_secret)
    if not token:
        sys.exit(1)

    file_key = upload_audio(token, tmp_opus)
    if not file_key:
        sys.exit(1)

    # Step 4: Send
    duration_ms = get_duration_ms(tmp_opus)
    print(f"[4/4] Sending voice to {receiver} (duration: {duration_ms}ms) ...")
    msg_id = send_message(
        token,
        receiver,
        "audio",
        json.dumps({"file_key": file_key, "duration": duration_ms}),
    )
    if msg_id:
        print(f"Done! message_id={msg_id}")
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()

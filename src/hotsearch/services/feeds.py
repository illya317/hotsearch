#!/usr/bin/env python3
"""Check new videos/releases/laws and push notifications via Feishu."""

from hotsearch.tools.feeds.newlaw import check_new_laws
from hotsearch.tools.feeds.newlaw_shanghai import check_new_shanghai_laws
from hotsearch.tools.feeds.release_feeds import check_new_releases
from hotsearch.tools.feeds.video_feeds import check_new_videos
from hotsearch.tools.system.feishu_send import send_to_feishu


def main():
    notifications = []
    notifications.extend(check_new_videos())
    notifications.extend(check_new_releases())
    notifications.extend(check_new_laws())
    notifications.extend(check_new_shanghai_laws())
    if notifications:
        msg = "🔔 新内容更新!\n\n" + "\n\n".join(notifications)
        print(msg)
        send_to_feishu(msg)
    else:
        print("No new content")


if __name__ == "__main__":
    main()

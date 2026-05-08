#!/bin/bash
# Anya 热搜监控定时任务
# 运行前自动 cd 到 hotsearch/ 根目录
cd "$(dirname "$0")/.."
export PYTHONPATH="$(pwd)/src${PYTHONPATH:+:$PYTHONPATH}"
export DATA_DIR=./data/cache

SCRIPT="src/hotsearch/services/scheduler.py"
NEWLAW="src/hotsearch/tools/search/newlaw.py"
NEWLAW_SH="src/hotsearch/tools/search/newlaw_shanghai.py"
SERVER_STATUS="src/hotsearch/tools/system/server-status.py"
LOG="./data/cache/cron.log"

case "$1" in
    push)
        python3 "$SCRIPT" push >> "$LOG" 2>&1
        ;;
    zhihu)
        python3 "$SCRIPT" zhihu >> "$LOG" 2>&1
        ;;
    weibo)
        python3 "$SCRIPT" weibo >> "$LOG" 2>&1
        ;;
    eastmoney)
        python3 "$SCRIPT" eastmoney >> "$LOG" 2>&1
        ;;
    ithome)
        python3 "$SCRIPT" ithome >> "$LOG" 2>&1
        ;;
    ainews)
        python3 "$SCRIPT" ainews >> "$LOG" 2>&1
        ;;
    github)
        python3 "$SCRIPT" github >> "$LOG" 2>&1
        ;;
    status)
        python3 "$SERVER_STATUS" >> "$LOG" 2>&1
        ;;
    newlaw)
        python3 "$NEWLAW" >> "$LOG" 2>&1
        ;;
    newlaw_shanghai)
        python3 "$NEWLAW_SH" >> "$LOG" 2>&1
        ;;
    *)
        echo "Usage: $0 {push|zhihu|weibo|eastmoney|ithome|ainews|github|status|newlaw|newlaw_shanghai}"
        exit 1
        ;;
esac

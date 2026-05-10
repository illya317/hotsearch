#!/bin/bash
# Anya 热搜监控定时任务编排
# 运行前自动 cd 到 hotsearch/ 根目录
cd "$(dirname "$0")/.."
export PYTHONPATH="$(pwd)/src${PYTHONPATH:+:$PYTHONPATH}"
export DATA_DIR=./data

CRON_CONFIG="config/cron.json"

# 读取 cron.json 中的顶层字段
_cron_json() {
    python3 -c "import json; cfg=json.load(open('$CRON_CONFIG')); print(cfg.get('$1',''))"
}

# 读取 cron.json 中的列表字段
_cron_list() {
    python3 -c "import json; cfg=json.load(open('$CRON_CONFIG')); print('\n'.join(cfg.get('$1',[])))"
}

# 读取指定任务的 script 路径
_script_for_task() {
    python3 -c "import json; cfg=json.load(open('$CRON_CONFIG')); print(cfg['tasks']['$1']['script'])"
}

# 读取 cron.json 中的 trends 任务名列表
_trends_tasks() {
    python3 -c "import json; cfg=json.load(open('$CRON_CONFIG')); print('\n'.join(cfg.get('trends',{}).keys()))"
}

# 创建目录
_cron_list directories | while read -r dir; do
    mkdir -p "$dir"
done

LOG="$(_cron_json log)"
mkdir -p "$(dirname "$LOG")"

# 检查参数是否在 trends 中
_is_trends_task() {
    _trends_tasks | grep -qx "$1"
}

case "$1" in
    feeds)
        SCRIPT="$(_script_for_task "$1")"
        # Step 1: 数据采集
        ./scripts/run.sh "$SCRIPT" >> "$LOG"
        ./scripts/run.sh "src/hotsearch/services/feeds.py" >> "$LOG"
        # Step 2: 分类+打分
        ./scripts/run.sh "src/hotsearch/agents/content.py" --source feeds >> "$LOG"
        # Step 3: 搜索增强+渲染+推送
        ./scripts/run.sh "src/hotsearch/agents/summary.py" --source feeds --send >> "$LOG"
        ;;
    status)
        SCRIPT="$(_script_for_task "$1")"
        ./scripts/run.sh "$SCRIPT" >> "$LOG"
        ;;
    *)
        if _is_trends_task "$1"; then
            # Step 1: 数据采集
            ./scripts/run.sh "src/hotsearch/services/trends.py" "$@" >> "$LOG"
            # Step 2: 分类+打分
            ./scripts/run.sh "src/hotsearch/agents/content.py" --source "$1" >> "$LOG"
            # Step 3: 搜索增强+渲染+推送
            ./scripts/run.sh "src/hotsearch/agents/summary.py" --source "$1" --send >> "$LOG"
        else
            echo "Usage: $0 {feeds|status|$(_trends_tasks | tr '\n' '|' | sed 's/|$//')}" >&2
            exit 1
        fi
        ;;
esac

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
TS=$(date +%Y%m%d_%H%M)

# 写日志：同时写入聚合日志和按步骤按时间戳的独立日志
_step_log() {
    local step="$1" mode="$2" script="$3"; shift 3
    local step_log="logs/${TS}_${step}_${mode}.log"
    echo "[$(date '+%H:%M:%S')] ${step}: ${mode}" | tee -a "$LOG" "$step_log"
    ./scripts/run.sh "$script" "$@" 2>&1 | tee -a "$LOG" "$step_log"
}

# 检查参数是否在 trends 中
_is_trends_task() {
    _trends_tasks | grep -qx "$1"
}

case "$1" in
    feeds)
        SCRIPT="$(_script_for_task "$1")"
        _step_log "step1_feeds"   "feeds" "$SCRIPT"
        _step_log "step1_collect" "feeds" "src/hotsearch/services/feeds.py"
        _step_log "step2_content" "feeds" "src/hotsearch/agents/content.py" --source feeds
        _step_log "step3_summary" "feeds" "src/hotsearch/agents/summary.py" --source feeds --send
        ;;
    status)
        SCRIPT="$(_script_for_task "$1")"
        _step_log "step1_status" "status" "$SCRIPT"
        ;;
    *)
        if _is_trends_task "$1"; then
            _step_log "step1_collect" "$1" "src/hotsearch/services/trends.py" "$@"
            _step_log "step2_content" "$1" "src/hotsearch/agents/content.py" --source "$1"
            _step_log "step3_summary" "$1" "src/hotsearch/agents/summary.py" --source "$1" --send
        else
            echo "Usage: $0 {feeds|status|$(_trends_tasks | tr '\n' '|' | sed 's/|$//')}" >&2
            exit 1
        fi
        ;;
esac

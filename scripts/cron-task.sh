#!/bin/bash
# Anya 热搜监控定时任务
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

# 读取 trends.json 中的任务名
_trends_tasks() {
    python3 -c "
import json
cfg = json.load(open('$(_cron_json trends_config)'))
print('\n'.join(cfg.get('tasks', {}).keys()))
"
}

# 创建目录
_cron_list directories | while read -r dir; do
    mkdir -p "$dir"
done

LOG="$(_cron_json log)"
mkdir -p "$(dirname "$LOG")"

# 检查参数是否在 trends.json 中
_is_trends_task() {
    _trends_tasks | grep -qx "$1"
}

case "$1" in
    feeds|status)
        SCRIPT="$(_script_for_task "$1")"
        ./scripts/run.sh "$SCRIPT" >> "$LOG" 2>&1
        ;;
    *)
        if _is_trends_task "$1"; then
            ./scripts/run.sh "src/hotsearch/services/trends.py" "$@" >> "$LOG" 2>&1
        else
            echo "Usage: $0 {feeds|status|$(_trends_tasks | tr '\n' '|' | sed 's/|$//')}"
            exit 1
        fi
        ;;
esac

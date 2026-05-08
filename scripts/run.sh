#!/bin/bash
# 运行任意 Python 脚本（.env 由 Python 自动加载）
# 用法: ./scripts/run.sh src/hotsearch/services/scheduler.py zhihu
cd "$(dirname "$0")/.."  # scripts/ → hotsearch/
export PYTHONPATH="$(pwd)/src${PYTHONPATH:+:$PYTHONPATH}"
export DATA_DIR=./data
exec python3 "$@"

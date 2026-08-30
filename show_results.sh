#!/usr/bin/env bash
# 一键看懂实验结果（不知道先看哪个文件就跑这个）
# 用法: bash show_results.sh [--samples]
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
if [ -f "${AMS_HOME:-$HOME/ams}/venv/bin/activate" ]; then
  source "${AMS_HOME:-$HOME/ams}/venv/bin/activate"
fi
exec python ams/analysis/show.py "$@"

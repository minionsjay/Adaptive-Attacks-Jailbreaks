#!/usr/bin/env bash
# ============================================================
# run_eval.sh — 在 V100 机器本机运行评估（单机模式入口）
# 用法:
#   bash remote/run_eval.sh --dry-run            # 先做连通性检查
#   bash remote/run_eval.sh --mode jailbreak --generations 3   # 小规模试跑
#   bash remote/run_eval.sh --mode full          # 正式全量
#   bash remote/run_eval.sh --mode report --exp-id exp_xxx     # 重出报告
# 其余参数原样传给 main.py
# ============================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"      # 项目根目录
cd "$HERE"
export PYTHONUNBUFFERED=1

# 激活本机 venv（setup_env.sh 创建）
if [ -f "${AMS_HOME:-$HOME/ams}/venv/bin/activate" ]; then
  source "${AMS_HOME:-$HOME/ams}/venv/bin/activate"
fi

# 首次运行引导：没有本地配置就从模板生成
if [ ! -f "$HERE/config.yaml" ] && [ -f "$HERE/config.yaml.example" ]; then
  cp "$HERE/config.yaml.example" "$HERE/config.yaml"
  echo "[bootstrap] 已从 config.yaml.example 生成本地 config.yaml（可自由修改）"
fi
CONFIG="${AMS_CONFIG:-$HERE/config.yaml}"
echo "[run_eval] 项目目录: $HERE"
echo "[run_eval] 配置: $CONFIG（单机模式，全部服务 localhost）"
echo "[run_eval] 参数: $*"

# 终端输出的同时全部落盘日志（含每一代、每条候选的实时行）
LOG_DIR="${AMS_LOG_DIR:-$HERE/redteam_output}/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/run_$(date +%Y%m%d_%H%M%S).log"
echo "[run_eval] 日志: $LOG"
exec > >(tee -a "$LOG") 2>&1

python main.py -c "$CONFIG" "$@"

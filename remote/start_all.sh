#!/usr/bin/env bash
# ============================================================
# start_all.sh — V100 机器一键启动全部服务（tmux 会话）
# 单机模式：服务 + 评估都在本机。
# 用法:
#   bash start_all.sh              # 只起服务（attacker/victim/detectors）
#   EVAL=1 bash start_all.sh       # 服务 + 自动开一个 eval 窗口跑评估
# 查看: tmux a -t ams
# ============================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SESSION="${SESSION:-ams}"

tmux kill-session -t "$SESSION" 2>/dev/null || true
tmux new-session -d -s "$SESSION" -n attacker  "bash $HERE/serve_attacker.sh; exec bash"
tmux new-window -d -t "$SESSION" -n victim     "bash $HERE/serve_victim.sh; exec bash"
tmux new-window -d -t "$SESSION" -n detectors  "bash $HERE/serve_detectors.sh; exec bash"

echo "已启动 tmux 会话 $SESSION（全部服务跑在本机）:"
echo "  tmux a -t ams                    # 查看各窗口日志"
echo "  curl -s http://127.0.0.1:8000/v1/models   # 攻击者 27B"
echo "  curl -s http://127.0.0.1:8001/v1/models   # victim"
echo "  curl -s http://127.0.0.1:8820/health      # 检测器"

if [ "${EVAL:-0}" = "1" ]; then
  tmux new-window -d -t "$SESSION" -n eval \
    "sleep 20 && bash $HERE/run_eval.sh --dry-run && bash $HERE/run_eval.sh --mode full; exec bash"
  echo "  eval 窗口已排队：等服务就绪后自动 dry-run + 全量评估"
else
  echo "  评估（另开窗口/会话）: bash remote/run_eval.sh --mode full"
fi

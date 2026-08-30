#!/usr/bin/env bash
# ============================================================
# serve_detectors.sh — 拉起被测检测器（2B / <1B，统一 /v1/detect 协议）
# 用法:
#   bash serve_detectors.sh                          # 默认三件套
#   DETECTORS="deberta-injection-v2 prompt-guard-86m" bash serve_detectors.sh
# 检测器跑本机 CPU 即可（86M~184M 单次 <100ms；2B 生成式建议 DEVICE=cuda:0
# —— 若显存紧张可与 27B 共卡：2B 半精度约 5GB，Q5_K_P 双卡各余 ~4GB 需评估）
# ============================================================
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"     # redteam/
DETECTORS="${DETECTORS:-deberta-injection-v2 prompt-guard-86m keyword-baseline}"
export DEVICE="${DEVICE:-cpu}"
# 读取统一路径配置 remote/models.env（HF_HOME 控制检测器下载位置）
ENV_FILE="$(cd "$(dirname "$0")" && pwd)/models.env"
[ -f "$ENV_FILE" ] && . "$ENV_FILE"
[ -n "${HF_HOME:-}" ] && export HF_HOME

source "${AMS_HOME:-$HOME/ams}/venv/bin/activate" 2>/dev/null || true

declare -A PORTS=(
  [prompt-guard-86m]=8810
  [prompt-guard-2-86m]=8811
  [prompt-guard-2-22m]=8812
  [prompt-guard-2-2b]=8813
  [deberta-injection-v2]=8820
  [deberta-injection-v1]=8821
  [keyword-baseline]=8830
  [ppl-window]=8840
  [llama-guard-3-1b]=8841
)

PIDS=()
cleanup() { for p in ${PIDS[@]:-}; do kill "$p" 2>/dev/null || true; done; }
trap cleanup EXIT INT TERM

for d in $DETECTORS; do
  port="${PORTS[$d]:-8899}"
  echo "[detector] $d -> :$port (device=$DEVICE)"
  ( cd "$HERE/detectors" && exec python serve_detector.py --id "$d" --port "$port" ) &
  PIDS+=($!)
  sleep 3
done

echo "[detector] 全部启动: ${PIDS[*]}"
wait

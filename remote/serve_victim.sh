#!/usr/bin/env bash
# ============================================================
# serve_victim.sh — 被攻击的 victim 模型（:8001）
# victim 必须是【安全对齐】模型（uncensored 当 victim 没有意义）。
# 2×V100 已被 27B 占满时跑 CPU 即可（victim 输出短、QPS 低）。
# 用法: VICTIM_MODEL=Qwen3-4B-Instruct-Q4_K_M bash serve_victim.sh
# ============================================================
set -euo pipefail

# 读取统一路径配置 remote/models.env
ENV_FILE="$(cd "$(dirname "$0")" && pwd)/models.env"
[ -f "$ENV_FILE" ] && . "$ENV_FILE"

AMS_HOME="${AMS_HOME:-$HOME/ams}"
MODEL_DIR="${MODEL_DIR:-$AMS_HOME/models}"
[ -n "${HF_HOME:-}" ] && export HF_HOME
VICTIM_MODEL="${VICTIM_MODEL:-Qwen3-4B-Instruct-Q4_K_M}"   # 任意对齐小模型 GGUF
PORT="${PORT:-8001}"
NGL="${NGL:-999}"        # 有富余显存→999 全上GPU；CPU→0
if [ -n "${VICTIM_GGUF:-}" ]; then
  TARGET="$VICTIM_GGUF"
else
  TARGET="$MODEL_DIR/victim-${VICTIM_MODEL}.gguf"
fi

# 未下载时自动拉官方 quant（llama.cpp 官方仓库提供主流模型 GGUF）
if [ ! -f "$TARGET" ]; then
  echo "[victim] 下载 $VICTIM_MODEL ..."
  source "$AMS_HOME/venv/bin/activate" 2>/dev/null || true
  hf download "Qwen/Qwen3-4B-Instruct-GGUF" "${VICTIM_MODEL}.gguf" \
    --local-dir "$AMS_HOME/models" && \
    mv "$AMS_HOME/models/${VICTIM_MODEL}.gguf" "$TARGET" || {
      echo "请手动放置 victim GGUF 到 $TARGET"; exit 1; }
fi

exec "$AMS_HOME/llama.cpp/build/bin/llama-server" \
  -m "$TARGET" --alias "Qwen3-4B-Instruct" \
  --host 0.0.0.0 --port "$PORT" \
  -ngl "$NGL" -c 8192 --jinja --parallel 2

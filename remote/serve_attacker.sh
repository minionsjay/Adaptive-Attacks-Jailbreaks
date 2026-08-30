#!/usr/bin/env bash
# ============================================================
# serve_attacker.sh — 2×V100 双卡拉起自进化攻击底座（llama-server :8000）
#
# 资源测算（2×V100-16G, 32G 总显存）:
#   Q5_K_P 20.2GB → tensor-split 各约 10.1GB + KV cache(16K ctx, q8_0 约 1.6GB/卡)
#   Q4_K_P 17.9GB → 各约 9.0GB，可开 32K ctx
# V100(Volta) 注意:
#   - 不支持 bf16 → GGUF 权重天然规避
#   - llama.cpp flash-attn 对 Volta 支持不稳 → 默认关闭（FA=0）
#   - MTP 加速: SPEC=embedded 用上游 --spec-type draft-mtp（无需补丁）
# ============================================================
set -euo pipefail

# 读取统一路径配置 remote/models.env（存在才读，变量可被环境变量覆盖）
ENV_FILE="$(cd "$(dirname "$0")" && pwd)/models.env"
[ -f "$ENV_FILE" ] && . "$ENV_FILE"

AMS_HOME="${AMS_HOME:-$HOME/ams}"
# 路径优先级: MODEL_PATH 环境变量 > models.env 的 ATTACKER_GGUF > MODEL_DIR 按 QUANT 拼名
MODEL_PATH="${MODEL_PATH:-${ATTACKER_GGUF:-}}"
MODEL_DIR="${MODEL_DIR:-$AMS_HOME/models}"
QUANT="${QUANT:-Q5_K_P}"
CTX="${CTX:-32768}"   # 注意: -c 会被 --parallel 平分（32K/4=每slot 8K）
PORT="${PORT:-8000}"
FA="${FA:-0}"                       # Volta 建议关
SPEC="${SPEC:-embedded}"            # embedded | off
export GGML_CUDA_ENABLE_UNIFIED_MEMORY=0

if [ -n "$MODEL_PATH" ]; then
  TARGET="$MODEL_PATH"
else
  TARGET="$MODEL_DIR/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-${QUANT}.gguf"
fi
[ -f "$TARGET" ] || { echo "缺少模型文件: $TARGET
解决方式（任选其一）:
  1) 编辑 remote/models.env 设 ATTACKER_GGUF=/你的路径/xxx.gguf   ← 推荐
  2) MODEL_PATH=/你的路径/xxx.gguf bash serve_attacker.sh
  3) bash download_model.sh 自动下载"; exit 1; }
echo "[attacker] 使用模型: $TARGET"

CMD=("$AMS_HOME/llama.cpp/build/bin/llama-server"
  -m "$TARGET"
  --alias "Qwen3.8-27B-Uncensored-Aggressive"
  --host 0.0.0.0 --port "$PORT"
  -ngl 999                          # 全层上 GPU
  --tensor-split 0.5,0.5            # 双卡均分
  -c "$CTX"
  --flash-attn "$FA"
  --jinja                           # 使用 GGUF 内置 Qwen3.8 chat template
  --parallel 4                      # mutator/critic 并发
  --cont-batching
)

case "$SPEC" in
  embedded) CMD+=(--spec-type draft-mtp) ;;        # 上游内嵌 MTP/NextN，免补丁
  off) ;;
esac

echo "[attacker] ${CMD[*]}"
exec "${CMD[@]}"

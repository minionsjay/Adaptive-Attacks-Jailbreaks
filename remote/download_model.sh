#!/usr/bin/env bash
# ============================================================
# download_model.sh — 下载 Qwen3.8-27B-Uncensored GGUF 到远程机器
# 默认 Q5_K_P（20.2GB ≈ 10.1GB/卡，2×V100-16G 推荐）
# 用法: QUANT=Q4_K_P bash download_model.sh
# ============================================================
set -euo pipefail

AMS_HOME="${AMS_HOME:-$HOME/ams}"
REPO="HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF"
QUANT="${QUANT:-Q5_K_P}"     # Q5_K_P(20.2G) | Q4_K_P(17.9G) | Q6_K_P(25.9G, 需小上下文)
TARGET="$AMS_HOME/models/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-${QUANT}.gguf"
DRAFT="$AMS_HOME/models/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-FastMTP-32K.gguf"

source "$AMS_HOME/venv/bin/activate" 2>/dev/null || pip install -U "huggingface_hub[cli]"
mkdir -p "$AMS_HOME/models"; cd "$AMS_HOME/models"

if [ ! -f "$TARGET" ]; then
  echo "[download] $TARGET"
  hf download "$REPO" \
    "Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-${QUANT}.gguf" \
    --local-dir "$AMS_HOME/models" || \
  curl -L -C - -o "$TARGET" \
    "https://huggingface.co/${REPO}/resolve/main/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-${QUANT}.gguf"
fi

# FastMTP sidecar（903MB，可选加速；embedded MTP 不需要它）
if [ ! -f "$DRAFT" ] && [ "${WITH_DRAFT:-0}" = "1" ]; then
  hf download "$REPO" \
    "Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-FastMTP-32K.gguf" \
    --local-dir "$AMS_HOME/models" || true
fi

# 校验
echo "[download] 校验 SHA256（与官方 SHA256SUMS 比对）"
curl -sL "https://huggingface.co/${REPO}/resolve/main/SHA256SUMS" | \
  grep "${QUANT}.gguf" > /tmp/ams_sha.txt || true
if [ -s /tmp/ams_sha.txt ]; then
  (cd "$AMS_HOME/models" && sha256sum -c /tmp/ams_sha.txt) || \
    echo "[download] ⚠️ 校验失败，请删除文件重下"
fi
ls -lh "$AMS_HOME/models/"

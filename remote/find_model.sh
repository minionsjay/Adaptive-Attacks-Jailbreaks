#!/usr/bin/env bash
# ============================================================
# find_model.sh — 自动找到你已下载的 GGUF 并放到约定位置
# 在 V100 机器上直接跑: bash find_model.sh
# ============================================================
set -euo pipefail
AMS_HOME="${AMS_HOME:-$HOME/ams}"
mkdir -p "$AMS_HOME/models"

echo "[find] 在常见位置搜索 *.gguf（>5GB 的大文件）……"
FOUND=$(find "$HOME" /data /mnt /opt /models /workspace -maxdepth 4 \
        -name "*Qwen3.8*27B*.gguf" -size +5G 2>/dev/null | head -5 || true)
if [ -z "$FOUND" ]; then
  echo "没找到 Qwen3.8-27B 的 GGUF。请确认："
  echo "  1) 文件是 .gguf 后缀（不是 safetensors —— llama.cpp 只认 GGUF）"
  echo "  2) 手动: MODEL_PATH=/你的路径/xxx.gguf bash serve_attacker.sh"
  exit 1
fi
echo "[find] 找到:"
echo "$FOUND" | sed 's/^/    /'
SRC=$(echo "$FOUND" | head -1)
FNAME=$(basename "$SRC")
DST="$AMS_HOME/models/$FNAME"

# 写入统一配置 models.env（ATTACKER_GGUF 指向真实路径，serve_attacker.sh 自动读取）
ENV_FILE="$(cd "$(dirname "$0")" && pwd)/models.env"
REAL="$(realpath "$SRC")"
if grep -q '^#ATTACKER_GGUF=' "$ENV_FILE" 2>/dev/null; then
  sed -i "s|^#ATTACKER_GGUF=.*|ATTACKER_GGUF=\"$REAL\"|" "$ENV_FILE"
  echo "[find] 已写入 $ENV_FILE: ATTACKER_GGUF=\"$REAL\""
else
  echo "" >> "$ENV_FILE"
  echo "ATTACKER_GGUF="$REAL"" >> "$ENV_FILE"
  echo "[find] 已追加到 $ENV_FILE: ATTACKER_GGUF=\"$REAL\""
fi
cat <<MSG

✅ 模型已配置。直接启动：
  bash serve_attacker.sh
MSG

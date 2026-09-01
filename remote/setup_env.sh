#!/usr/bin/env bash
# ============================================================
# setup_env.sh — 远程 2×V100 机器环境准备（一次执行）
# 产出: ~/ams/llama.cpp/build/bin/llama-server + Python venv
# ============================================================
set -euo pipefail

AMS_HOME="${AMS_HOME:-$HOME/ams}"
# REPO = 项目仓库在本机的位置（单机模式：服务 + runner 都在这台机器）
REPO="${REPO:-$(cd "$(dirname "$0")/.." && pwd)}"
echo "[setup] AMS_HOME=$AMS_HOME  (模型与 llama.cpp)"
echo "[setup] REPO=$REPO  (项目仓库；runner 也将在此运行)"
mkdir -p "$AMS_HOME"/models && cd "$AMS_HOME"

# ---------- 系统依赖（按需调整包管理器）----------
if command -v apt-get >/dev/null; then
  sudo apt-get update -y
  sudo apt-get install -y build-essential cmake curl git libcurl4-openssl-dev python3-venv
fi

# ---------- Python venv（服务 + runner 共用）----------
if [ ! -d "$AMS_HOME/venv" ]; then
  python3 -m venv "$AMS_HOME/venv"
fi
source "$AMS_HOME/venv/bin/activate"
pip install -U pip
# torch（CUDA 版优先；失败回落 CPU 版）
pip install torch --index-url https://download.pytorch.org/whl/cu121 || pip install torch
# 项目全部依赖（runner ams 包 + 检测器 transformers 后端 + 服务）
pip install -r "$REPO/requirements.txt"

# ---------- llama.cpp（自动检测 GPU 后端: CUDA / ROCm(HIP) / Vulkan / CPU）----------
if [ ! -d "$AMS_HOME/llama.cpp" ]; then
  git clone https://github.com/ggerganov/llama.cpp "$AMS_HOME/llama.cpp"
fi
cd "$AMS_HOME/llama.cpp"

# 后端检测（可用 LLAMA_BACKEND=hip|cuda|vulkan|cpu 强制指定）
detect_backend() {
  if [ -n "${LLAMA_BACKEND:-}" ]; then echo "$LLAMA_BACKEND"; return; fi
  if command -v rocm-smi >/dev/null 2>&1; then echo "hip"
  elif command -v nvidia-smi >/dev/null 2>&1; then echo "cuda"
  else echo "cpu"; fi
}
BACKEND="$(detect_backend)"
echo "[setup] llama.cpp 后端: $BACKEND"
case "$BACKEND" in
  hip)
    GFX_TARGET=$(rocminfo 2>/dev/null | grep -m1 -oE "gfx[0-9a-f]+" || true)
    echo "[setup] AMD GPU target: ${GFX_TARGET:-未检出,用默认}"
    BUILD_FLAGS=(-DGGML_HIP=ON)
    [ -n "$GFX_TARGET" ] && BUILD_FLAGS+=(-DAMDGPU_TARGETS="$GFX_TARGET")
    ;;
  cuda) BUILD_FLAGS=(-DGGML_CUDA=ON) ;;
  vulkan) BUILD_FLAGS=(-DGGML_VULKAN=ON) ;;
  *) BUILD_FLAGS=() ;;
esac

# （FastMTP 补丁可选；构建后端已自动检测，见上方 detect_backend）
if [ "${FASTMTP_PATCH:-0}" = "1" ]; then
  curl -L -o HauhauCS-FastMTP-llama.cpp.patch \
    "https://huggingface.co/HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF/resolve/main/HauhauCS-FastMTP-llama.cpp.patch"
  git apply --check HauhauCS-FastMTP-llama.cpp.patch || true
  git apply HauhauCS-FastMTP-llama.cpp.patch || echo "[setup] FastMTP patch 跳过（可能已应用）"
fi

cmake -S . -B build -DCMAKE_BUILD_TYPE=Release "${BUILD_FLAGS[@]}"
cmake --build build --config Release -j"$(nproc)"
"$AMS_HOME/llama.cpp/build/bin/llama-server" --version || true

cat <<EOF
[setup] 完成（venv 含 runner + 服务全部依赖）。单机模式下一步:
  1) cd $REPO/remote
  2) bash download_model.sh                # 下载 27B GGUF（默认 Q5_K_P, 20.2GB）
  3) EVAL=1 bash start_all.sh              # tmux 一键: attacker+victim+detectors+评估
     或分步: bash start_all.sh && bash run_eval.sh --dry-run
  4) bash run_eval.sh --mode jailbreak --generations 3   # 先小规模试跑
  5) bash run_eval.sh --mode full          # 正式全量（结果在 $REPO/redteam_output/）
结果查看/取回（在开发机上）:
  ssh v100 'cat ~/ams-redteam/redteam_output/report_*.md'
  scp v100:~/ams-redteam/redteam_output/report_*.md .
EOF

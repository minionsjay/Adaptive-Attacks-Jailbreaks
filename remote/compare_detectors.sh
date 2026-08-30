#!/usr/bin/env bash
# ============================================================
# compare_detectors.sh — 横向对比多个检测器的检测能力（一键脚本）
#
# 做什么：对每个检测器 → 单独拉起 → 单独跑一轮评估 → 存报告 → 关掉
#         → 最后汇总成 comparison.md 排行榜。
#
# 用法（V100 机器，项目根目录）:
#   # 默认对比 3 个免登录检测器: 规则 / DeBERTa 184M / PPL窗(1.5B底座):
#   bash remote/compare_detectors.sh
#
#   # 自定义名单 / 模式 / 规模:
#   DETECTORS_TO_COMPARE="keyword-baseline deberta-injection-v2 prompt-guard-86m ppl-window" \
#     MODE=jailbreak GENERATIONS=5 POPULATION=6 bash remote/compare_detectors.sh
#
#   MODE=full 也会跑 6 个注入场景（更久）
# 结果: redteam_output_compare/comparison.md  ← 最终排行榜
# ============================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"

# venv（没有就用当前 python —— 前提是已装 requirements.txt）
if [ -f "${AMS_HOME:-$HOME/ams}/venv/bin/activate" ]; then
  source "${AMS_HOME:-$HOME/ams}/venv/bin/activate"
fi

LIST="${DETECTORS_TO_COMPARE:-keyword-baseline deberta-injection-v2 ppl-window}"
MODE="${MODE:-jailbreak}"
GEN="${GENERATIONS:-5}"
POP="${POPULATION:-6}"
# 首次运行引导：没有本地配置就从模板生成
if [ ! -f "$HERE/config.yaml" ] && [ -f "$HERE/config.yaml.example" ]; then
  cp "$HERE/config.yaml.example" "$HERE/config.yaml"
  echo "[bootstrap] 已从 config.yaml.example 生成本地 config.yaml（可自由修改）"
fi
OUT="${COMPARE_OUT:-redteam_output_compare}"
CFG=/tmp/ams_compare_cfg.yaml
mkdir -p "$OUT"

# 终端输出的同时全部落盘日志
LOG_DIR="$OUT/logs"; mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/compare_$(date +%Y%m%d_%H%M%S).log"
echo "[compare] 日志: $LOG"
exec > >(tee -a "$LOG") 2>&1

# 路径配置（HF_HOME 等）
ENV_FILE="$HERE/remote/models.env"
[ -f "$ENV_FILE" ] && . "$ENV_FILE"
[ -n "${HF_HOME:-}" ] && export HF_HOME

for d in $LIST; do
  echo ""
  echo "════════════════════════════════════════════════════════"
  echo "  检测器: $d"
  echo "════════════════════════════════════════════════════════"
  PORT=$(python - <<PY
from detectors.registry import DETECTORS
print(DETECTORS["$d"]["default_url"].rsplit(":",1)[-1])
PY
)
  # 拉起该检测器（首次运行会下载模型，等待上限 15 分钟）
  ( cd detectors && exec python serve_detector.py --id "$d" --port "$PORT" ) &
  DETPID=$!
  READY=0
  for i in $(seq 1 180); do
    if curl -s --max-time 3 "http://127.0.0.1:$PORT/health" 2>/dev/null | grep -q '"ok":true'; then
      READY=1; break
    fi
    # 进程已死（如下载失败崩溃）→ 立刻跳出，不傻等 15 分钟
    if ! kill -0 $DETPID 2>/dev/null; then
      echo "  ✗ 检测器进程退出（常见: 模型下载失败——配 models.env 的 HF_ENDPOINT 镜像或本地路径）"
      break
    fi
    sleep 5
  done
  if [ "$READY" != "1" ]; then
    echo "  ✗ $d 启动/下载超时，跳过"; kill $DETPID 2>/dev/null || true; continue
  fi
  echo "  ✓ 服务就绪 :$PORT"

  # 生成单检测器配置（输出统一到 $OUT；GEN/POP 走环境变量）
  GEN="$GEN" POP="$POP" python - "$d" "$OUT" <<'PY'
import os, sys, yaml
det, out = sys.argv[1], sys.argv[2]
cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
cfg["detectors"] = [det]
cfg["output"]["dir"] = out
cfg["evolution"]["max_generations"] = int(os.environ.get("GEN", 5))
cfg["evolution"]["population_size"] = int(os.environ.get("POP", 6))
cfg["evolution"]["injection_generations"] = min(
    int(os.environ.get("GEN", 5)), cfg["evolution"].get("injection_generations", 8))
yaml.safe_dump(cfg, open("/tmp/ams_compare_cfg.yaml", "w", encoding="utf-8"),
               allow_unicode=True)
PY

  echo "  ▶ 评估开始 ($MODE, ${GEN}代 × ${POP}候选)"
  python main.py -c "$CFG" --mode "$MODE" || echo "  ✗ 评估出错（继续下一个）"

  kill $DETPID 2>/dev/null || true
  wait $DETPID 2>/dev/null || true
done

echo ""
echo "════════════════════════════════════════════════════════"
echo "  汇总对比"
echo "════════════════════════════════════════════════════════"
python ams/analysis/compare.py --dir "$OUT"

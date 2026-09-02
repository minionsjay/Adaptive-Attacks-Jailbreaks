#!/usr/bin/env bash
# ============================================================
# sweep_victims.sh — 多 victim 鲁棒性横扫（论文表1式实验）
# 同攻击者(火山glm-5.2)、同种子、同代数，横扫多个被攻击模型
# 结果: redteam_output_victims/<model>/ + 汇总表
# 用法:
#   bash remote/sweep_victims.sh                       # 默认 4 个国产+gpt
#   VICTIMS="gpt-4o deepseek-v3 qwen3-max glm-4.7" bash remote/sweep_victims.sh
#   GENERATIONS=3 POPULATION=4 SWEEP_DETECTOR=keyword-baseline bash ...
# ============================================================
set -uo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"
export PYTHONUNBUFFERED=1
if [ -f "${AMS_HOME:-$HOME/ams}/venv/bin/activate" ]; then
  source "${AMS_HOME:-$HOME/ams}/venv/bin/activate"
fi

VICTIMS="${VICTIMS:-gpt-4o deepseek-v3 qwen3-max glm-4.7}"
GEN="${GENERATIONS:-3}"
POP="${POPULATION:-4}"
DET="${SWEEP_DETECTOR:-keyword-baseline}"
OUTROOT="redteam_output_victims"
mkdir -p "$OUTROOT"

for v in $VICTIMS; do
  echo ""
  echo "══════════════════════════════════════════════"
  echo "  victim = $v   (GEN=$GEN POP=$POP det=$DET)"
  echo "══════════════════════════════════════════════"
  OUT="$OUTROOT/$v"
  mkdir -p "$OUT"
  GEN="$GEN" POP="$POP" DET="$DET" OUT="$OUT" VICTIM="$v" python3 - <<'PY'
import os, sys, yaml
cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
cfg["victim"]["model"] = os.environ["VICTIM"]
cfg["detectors"] = [os.environ["DET"]]
cfg["evolution"]["max_generations"] = int(os.environ["GEN"])
cfg["evolution"]["population_size"] = int(os.environ["POP"])
cfg["output"]["dir"] = os.environ["OUT"]
path = f"/tmp/sweep_{os.environ['VICTIM'].replace('/', '_')}.yaml"
yaml.safe_dump(cfg, open(path, "w", encoding="utf-8"), allow_unicode=True)
print(f"  [cfg] {path}")
PY
  python3 main.py -c "/tmp/sweep_${v//\//_}.yaml" --mode jailbreak \
    || echo "  ✗ $v 失败（继续下一个）"
done

echo ""
echo "════════════════ 汇总 ════════════════"
python3 scripts/summarize_victims.py --dir "$OUTROOT" || true

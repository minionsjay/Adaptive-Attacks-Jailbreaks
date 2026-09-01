#!/usr/bin/env bash
# ============================================================
# download_small_models.sh — 一键下载被测小模型到指定目录
#
# 用法:
#   bash remote/download_small_models.sh /data/models                 # 全部无门控(检测器+推荐victim)
#   bash remote/download_small_models.sh /data/models detectors       # 只下无门控检测器(≈4.5GB)
#   bash remote/download_small_models.sh /data/models victims         # 只下推荐victim三件套(≈7GB)
#   bash remote/download_small_models.sh /data/models victims-all     # 全部无门控victim(≈15GB)
#   bash remote/download_small_models.sh /data/models deberta-injection-v2 prompt-guard-86m
#   bash remote/download_small_models.sh /data/models victim:smollm2-360m
# 选项:
#   --with-gated   连门控模型一起下（先 huggingface-cli login + 网页接受许可）
#   --write-env    下载后自动写入 remote/models.env
#   --dry-run      只列清单不下载
# ============================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"

DIR=""
SELS=()
WITH_GATED=0 WRITE_ENV=0 DRY=0
for a in "$@"; do
  case "$a" in
    --with-gated) WITH_GATED=1 ;;
    --write-env)  WRITE_ENV=1 ;;
    --dry-run)    DRY=1 ;;
    -h|--help)    sed -n '2,17p' "$0"; exit 0 ;;
    *)  if [ -z "$DIR" ]; then DIR="$a"; else SELS+=("$a"); fi ;;
  esac
done
[ -z "$DIR" ] && { sed -n '2,17p' "$0"; exit 1; }
[ ${#SELS[@]} -eq 0 ] && SELS=("all")
mkdir -p "$DIR"

# ---------- 展开"选择器 → 模型清单"（TSV: kind  reg_id  hf_id  gated） ----------
PLAN=$(WITH_GATED=$WITH_GATED python3 - "${SELS[@]}" <<'PY'
import os, sys
from detectors.registry import DETECTORS
from ams.victim_registry import VICTIMS

sels = sys.argv[1:]
with_gated = os.environ.get("WITH_GATED") == "1"

# 实测(401探测): meta-llama 全系(含86M/22M)都需 HF 账号接受许可
NON_GATED_DET = ["deberta-injection-v2", "deberta-injection-v1", "ppl-window",
                 "qwen3guard-0.6b", "granite-guardian-2b"]
GATED_DET = ["prompt-guard-86m", "prompt-guard-2-86m", "prompt-guard-2-22m",
             "prompt-guard-2-2b", "llama-guard-3-1b"]
VICTIM_CORE = ["qwen2.5-1.5b", "smollm2-360m", "r1-distill-qwen-1.5b"]
VICTIM_ALL = [k for k, v in VICTIMS.items()
              if not v.get("gated") and v.get("group") != "baseline"]
GATED_VICTIMS = [k for k, v in VICTIMS.items() if v.get("gated")]

plan = []
def add_det(r):
    d = DETECTORS.get(r)
    if d and d.get("model_id"):
        plan.append(("det", r, d["model_id"], bool(d.get("requires"))))
def add_vic(r):
    if r in VICTIMS:
        plan.append(("victim", r, VICTIMS[r]["hf_id"], bool(VICTIMS[r].get("gated"))))

for s in sels:
    if s == "detectors":
        for r in NON_GATED_DET: add_det(r)
    elif s == "victims":
        for r in VICTIM_CORE: add_vic(r)
    elif s == "victims-all":
        for r in VICTIM_ALL: add_vic(r)
    elif s == "all":
        for r in NON_GATED_DET: add_det(r)
        for r in VICTIM_CORE: add_vic(r)
    elif s.startswith("victim:"):
        add_vic(s.split(":", 1)[1])
    elif s in DETECTORS:
        add_det(s)
    else:
        print(f"未知选择器: {s}", file=sys.stderr); sys.exit(1)

if with_gated:
    for r in GATED_DET: add_det(r)
    for r in GATED_VICTIMS: add_vic(r)

seen, out = set(), []
for row in plan:
    if row[2] in seen: continue
    seen.add(row[2]); out.append(row)
for row in out:
    print("\t".join(str(x) for x in row))
PY
)
[ -n "$PLAN" ] || { echo "没有匹配的模型"; exit 1; }

# ---------- 下载 ----------
DL() {
  if command -v hf >/dev/null 2>&1; then
    hf download "$1" --local-dir "$2"
  else
    huggingface-cli download "$1" --local-dir "$2"
  fi
}

echo "════════════════════════════════════════════════════════"
echo " 目标目录: $DIR"
echo " 清单:"
echo "$PLAN" | awk -F'\t' '{printf "   [%s] %-24s %s%s\n", $1, $2, $3, ($4=="True"?"  (门控,需login)":"")}'
echo "════════════════════════════════════════════════════════"

OK_DET=(); OK_VIC=()
while IFS=$'\t' read -r kind reg_id hf_id gated; do
  sub="$DIR/$(basename "$hf_id")"
  echo ""
  echo "▶ [$kind] $reg_id  →  $sub"
  [ "$DRY" = "1" ] && continue
  if [ "$gated" = "True" ]; then
    echo "  （门控模型；若 401/403：huggingface-cli login + 网页接受许可后重试）"
  fi
  if DL "$hf_id" "$sub"; then
    echo "  ✓ 完成"
    if [ "$kind" = "det" ]; then OK_DET+=("$reg_id=$sub"); else OK_VIC+=("$sub"); fi
  else
    echo "  ✗ 失败（跳过）"
  fi
done <<< "$PLAN"

[ "$DRY" = "1" ] && { echo ""; echo "[dry-run] 未下载。"; exit 0; }

# ---------- 生成/写入 models.env ----------
ENVF="$HERE/remote/models.env"
DET_LINE=""
[ ${#OK_DET[@]} -gt 0 ] && DET_LINE="DETECTOR_MODEL_OVERRIDES=\"$(IFS=,; echo "${OK_DET[*]}")\""
VIC_LINE=""
[ ${#OK_VIC[@]} -gt 0 ] && VIC_LINE="VICTIM_HF_MODEL=\"${OK_VIC[0]}\""

echo ""
if [ "$WRITE_ENV" = "1" ]; then
  python3 - "$ENVF" "$DET_LINE" "$VIC_LINE" <<'PY'
import re, sys
path, det, vic = sys.argv[1], sys.argv[2], sys.argv[3]
s = open(path, encoding="utf-8").read()
def upsert(s, line):
    if not line:
        return s
    key = line.split("=", 1)[0]
    if re.search(rf'^{key}=', s, re.M):
        return re.sub(rf'^{key}=.*$', line, s, flags=re.M)
    return s.rstrip() + "\n" + line + "\n"
s = upsert(s, det)
s = upsert(s, vic)
open(path, "w", encoding="utf-8").write(s)
print(f"✓ 已写入 {path}")
PY
else
  echo "✅ 下载完成。把下面几行加进 remote/models.env 即可启用本地路径："
  [ -n "$DET_LINE" ] && echo "  $DET_LINE"
  [ -n "$VIC_LINE" ] && echo "  $VIC_LINE"
  echo "（或用 --write-env 参数自动写入）"
fi

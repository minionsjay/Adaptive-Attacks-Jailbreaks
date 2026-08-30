#!/usr/bin/env bash
# ============================================================
# run_smoke.sh — 本地无 GPU 冒烟：mock LLM + 规则/真实检测器
# 验证: 进化循环 / 注入场景 / 报告 / 训练数据导出 全链路
# 用法:
#   bash scripts/run_smoke.sh                # 规则基线（零下载）
#   bash scripts/run_smoke.sh --real         # 附加真实 DeBERTa 184M（首次下载~184MB）
# ============================================================
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
cd "$HERE"

MOCK_PORT=9077
SMOKE_CFG=/tmp/ams_smoke_config.yaml

cleanup() { pkill -f "mock_llm.py --port $MOCK_PORT" 2>/dev/null || true
            pkill -f "serve_detector.py --id keyword-baseline" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

echo "[smoke] 1/4 启动 mock LLM (:$MOCK_PORT)"
python scripts/mock_llm.py --port $MOCK_PORT &
sleep 2

echo "[smoke] 2/4 启动 keyword-baseline 检测器 (:8830)"
( cd detectors && python serve_detector.py --id keyword-baseline --port 8830 ) &
sleep 2

DETS='[keyword-baseline]'
if [ "${1:-}" = "--real" ]; then
  echo "[smoke] 2b 启动真实 DeBERTa 检测器 (:8820, 首次运行会下载模型)"
  ( cd detectors && python serve_detector.py --id deberta-injection-v2 --port 8820 ) &
  DETS='[keyword-baseline, deberta-injection-v2]'
  sleep 5
fi

echo "[smoke] 3/4 生成冒烟配置"
python - "$DETS" "$MOCK_PORT" <<'PYEOF'
import sys, yaml
dets = yaml.safe_load(sys.argv[1].replace(",", ", ")) if False else sys.argv[1].strip("[]").split(", ")
cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
mock = f"http://127.0.0.1:{sys.argv[2]}/v1"
for role in ("attacker", "critic", "victim"):
    if role in cfg:
        cfg[role]["base_url"] = mock
        cfg[role]["model"] = "mock-attacker" if role != "victim" else "mock-victim"
        cfg[role].pop("api_key_env", None)
cfg["judge"]["base_url"] = mock
cfg["judge"]["model"] = "mock-attacker"
cfg["judge"].pop("api_key_env", None)
cfg["detectors"] = dets
cfg["evolution"]["max_generations"] = 3
cfg["evolution"]["injection_generations"] = 2
cfg["evolution"]["population_size"] = 4
cfg["evolution"]["early_stop_min_gen"] = 99
cfg["output"]["dir"] = "./redteam_output_smoke"
yaml.safe_dump(cfg, open("/tmp/ams_smoke_config.yaml", "w", encoding="utf-8"),
               allow_unicode=True)
print("[smoke] 配置写入 /tmp/ams_smoke_config.yaml")
PYEOF

echo "[smoke] 4/4 运行评估（jailbreak 3代 + 全部注入场景）"
python main.py -c /tmp/ams_smoke_config.yaml --mode full
echo "[smoke] 完成 ✔  产物见 redteam_output_smoke/"

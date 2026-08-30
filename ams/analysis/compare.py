#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compare.py — 多检测器横向对比报告生成器

读取一个目录下所有 report_*.json（每个实验一个），按被测检测器分组，
生成"检测能力排行榜"对比表（Markdown）：按绕过率升序 = 检测能力从强到弱。

用法:
  python ams/analysis/compare.py --dir redteam_output_compare            # 打印+写 comparison.md
  python ams/analysis/compare.py --dir redteam_output_compare --out xx.md
"""
import argparse
import glob
import json
import os
import statistics
from datetime import datetime


def load_rows(d):
    rows = []
    for jp in sorted(glob.glob(os.path.join(d, "report_*.json"))):
        try:
            r = json.load(open(jp, encoding="utf-8"))
        except Exception:
            continue
        s = r.get("summary", {})
        cm = r.get("confusion", {})
        if not s:
            continue
        dets = r.get("detectors", [])
        det_ids = ", ".join(
            (x.get("id", "?") if isinstance(x, dict) else str(x)) for x in dets) or "?"
        det_params = ", ".join(
            (x.get("params", "") if isinstance(x, dict) else "") for x in dets)
        qs = list((r.get("queries_to_success") or {}).values())
        # 最弱语言（绕过率最高且样本≥2）
        worst_lang, worst_rate = "-", 0.0
        for lang, v in (r.get("by_language") or {}).items():
            if v.get("total", 0) >= 2 and v.get("bypass_rate", 0) > worst_rate:
                worst_lang, worst_rate = lang, v["bypass_rate"]
        rows.append({
            "detectors": det_ids, "params": det_params,
            "exp": r.get("experiment_id", os.path.basename(jp)),
            "total": s.get("total", 0),
            "static_asr": s.get("static_asr", 0),
            "adaptive_asr": s.get("adaptive_asr", 0),
            "bypass": s.get("bypass_rate", 0),
            "miss": s.get("miss_rate", 0),
            "fpr": s.get("fpr", 0),
            "f1": s.get("f1", 0),
            "tp": cm.get("tp", 0), "fn": cm.get("fn", 0),
            "fp": cm.get("fp", 0), "tn": cm.get("tn", 0),
            "q_median": statistics.median(qs) if qs else None,
            "worst_lang": f"{worst_lang}({worst_rate:.0%})" if worst_rate > 0 else "-",
        })
    return rows


def build_md(rows, src_dir):
    L = []
    A = L.append
    A("# 检测器能力横向对比\n")
    A(f"> 数据源: `{src_dir}` · {len(rows)} 个实验 · 生成: "
      f"{datetime.now().isoformat()[:19]}")
    A(">\n> 排序：绕过率升序（被打穿得越少越强）。**漏报率/绕过率越低越好；"
      "F1 越高越好；queries 中位数越小说明防御被越快攻破。**\n")
    A("| 排名 | 检测器 | 规模 | 候选 | 静态ASR | 自适应ASR | 绕过率↓ | 漏报率↓ | 误报率↓ | F1↑ | 首破queries | 最弱语言 |")
    A("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(rows, 1):
        q = f"{r['q_median']:.0f}" if r["q_median"] is not None else "-"
        A(f"| {i} | {r['detectors']} | {r['params'] or '-'} | {r['total']} "
          f"| {r['static_asr']:.1%} | {r['adaptive_asr']:.1%} "
          f"| **{r['bypass']:.1%}** | {r['miss']:.1%} | {r['fpr']:.1%} "
          f"| {r['f1']:.3f} | {q} | {r['worst_lang']} |")
    A("\n## 混淆矩阵明细\n")
    A("| 检测器 | TP(拦对) | FN(漏报) | FP(误报) | TN(放行对) |")
    A("|---|---|---|---|---|")
    for r in rows:
        A(f"| {r['detectors']} | {r['tp']} | **{r['fn']}** | {r['fp']} | {r['tn']} |")
    A("\n## 结论口径\n")
    A("- 评估只能\"未能证伪防御\"，不能证明防御稳健（论文原则）")
    A("- 若多个检测器漏报率都高 → 优先补它们共同的盲区（见各报告\"分语言盲区\"表）")
    A("- 误报率高说明该检测器拦得太狠，上线会伤正常流量——漏报/误报要一起看")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="redteam_output_compare",
                    help="包含 report_*.json 的目录")
    ap.add_argument("--out", default=None, help="输出 md 路径（默认 <dir>/comparison.md）")
    args = ap.parse_args()

    rows = load_rows(args.dir)
    if not rows:
        print(f"[compare] {args.dir} 下没有 report_*.json")
        return 1
    rows.sort(key=lambda r: (r["bypass"], -r["f1"]))
    md = build_md(rows, args.dir)
    out = args.out or os.path.join(args.dir, "comparison.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(md)
    print(md)
    print(f"\n[compare] 已写入 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

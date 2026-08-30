#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
show.py — 一键看懂实验结果（不知道先看哪个文件就用它）

用法:
  python ams/analysis/show.py                          # 自动找结果目录
  python ams/analysis/show.py --dir redteam_output_compare
  python ams/analysis/show.py --samples                # 附带展示 Top 绕过攻击原文
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from ams.analysis.compare import load_rows


def find_dir():
    for d in ("redteam_output_compare", "redteam_output",
              "redteam_output_smoke2", "redteam_output_smoke"):
        if glob.glob(os.path.join(d, "report_*.json")):
            return d
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=None)
    ap.add_argument("--samples", action="store_true", help="展示 Top 绕过攻击原文")
    args = ap.parse_args()

    d = args.dir or find_dir()
    if not d or not glob.glob(os.path.join(d, "report_*.json")):
        print("没找到任何 report_*.json —— 还没跑过实验，或结果在别的目录。")
        print("先跑: bash remote/compare_detectors.sh")
        return 1

    print("═" * 62)
    print(f"  实验结果速览   目录: {d}")
    print("═" * 62)
    rows = load_rows(d)
    rows.sort(key=lambda r: (r["bypass"], -r["f1"]))

    # ---------- 排行榜 ----------
    print("\n📊 检测器排行榜（绕过率升序 = 最耐打的排最前）\n")
    print(f"  {'#':<3}{'检测器':<28}{'绕过率↓':>9}{'漏报率↓':>9}{'误报率↓':>9}{'F1↑':>8}{'首破q':>7}")
    print("  " + "-" * 78)
    for i, r in enumerate(rows, 1):
        q = f"{r['q_median']:.0f}" if r["q_median"] is not None else "-"
        print(f"  {i:<3}{r['detectors'][:26]:<28}{r['bypass']:>8.1%}{r['miss']:>9.1%}"
              f"{r['fpr']:>9.1%}{r['f1']:>8.3f}{q:>7}")
    print("""
  数字怎么读：
    绕过率 = 骗过检测器且真的攻击成功的比例 —— 检测器的失分，越低越好
    漏报率 = 所有成功攻击里被放行的比例 —— ★最核心，直接就是"保安漏放了多少"
    误报率 = 无害内容被拦的比例 —— 误伤正常用户，要和漏报率一起看（只压一个没意义）
    F1     = 拦截的综合准确度
    首破q  = 攻击者平均花几次查询找到第一个绕过 —— 越小防御越脆""")

    # ---------- 每个实验详情 ----------
    print("📋 每个实验在测什么、发现了什么\n")
    for jp in sorted(glob.glob(os.path.join(d, "report_*.json"))):
        r = json.load(open(jp, encoding="utf-8"))
        s = r.get("summary", {})
        dets = ", ".join(x.get("id", "?") if isinstance(x, dict) else str(x)
                         for x in r.get("detectors", []))
        if os.path.basename(jp) == "comparison.json":
            continue
        print(f"  ● 实验 {r.get('experiment_id','?')}  被测: {dets}")
        print(f"    静态ASR {s.get('static_asr',0):.0%} → 自适应ASR {s.get('adaptive_asr',0):.0%}"
              f"  |  候选 {s.get('total',0)} 条")
        wl = [(k, v) for k, v in (r.get("by_language") or {}).items()
              if v.get("bypass_rate", 0) >= 0.5 and v.get("total", 0) >= 2]
        if wl:
            wl.sort(key=lambda x: -x[1]["bypass_rate"])
            langs = ", ".join(f"{k}({v['bypass_rate']:.0%})" for k, v in wl[:4])
            print(f"    ⚠️ 语言盲区: {langs}")
        qs = r.get("queries_to_success") or {}
        if qs:
            print(f"    首次成功成本: " + "  ".join(f"{k.split('|')[-1]}={v}次"
                                              for k, v in list(qs.items())[:3]))
        recs = r.get("recommendations") or []
        if recs:
            print(f"    改进建议#1: {recs[0][:76]}")
        print(f"    完整报告: {jp.replace('.json','.md')}\n")

    # ---------- 样本 ----------
    if args.samples:
        print('🗡️ Top 绕过攻击样本（进化搜索【发明】出来的攻击原文）\n')
        for jp in sorted(glob.glob(os.path.join(d, "report_*.json"))):
            r = json.load(open(jp, encoding="utf-8"))
            tops = r.get("top_bypassed") or []
            if not tops:
                continue
            print(f"  —— {r.get('experiment_id')} ——")
            for t in tops[:5]:
                print(f"   [{t.get('attack_type')}|{t.get('language')}] "
                      f"det={t.get('det_score',0):.2f} | "
                      f"{(t.get('prompt') or '')[:80]}")
            print()

    # ---------- 深入入口 ----------
    print("📂 想再深入，按需打开这些\n")
    print("  攻击者(27B)每代看到什么/说了什么 →  mutator_io/gen1.txt, gen2.txt ...")
    print("  每条攻击的完整数据(检测分/回复/判定) →  candidates.jsonl（每行一条JSON）")
    print("  某条攻击被谁拦/为什么拦            →  llm_io/judge.jsonl, critic.jsonl")
    print("  整个过程终端回放                   →  logs/compare_*.log")
    print("  可喂检测器对抗训练的回流数据        →  exports/training_data_*.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

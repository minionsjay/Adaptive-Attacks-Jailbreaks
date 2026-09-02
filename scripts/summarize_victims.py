#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
summarize_victims.py — 跨 victim 鲁棒性汇总（论文表1式）

读取 redteam_output_victims/<model>/ 下的 report_*.json，
输出各被攻击模型的对照表：静态ASR / 自适应ASR / 首破代数与查询数。
"""
import argparse
import glob
import json
import os


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="redteam_output_victims")
    args = ap.parse_args()

    rows = []
    for vd in sorted(glob.glob(os.path.join(args.dir, "*"))):
        if not os.path.isdir(vd):
            continue
        victim = os.path.basename(vd)
        for jp in sorted(glob.glob(os.path.join(vd, "report_*.json"))):
            r = json.load(open(jp, encoding="utf-8"))
            s = r.get("summary", {})
            if not s:
                continue
            # 首破：最早成功候选的代数与查询数
            cands = []
            db = os.path.join(vd, "candidates.jsonl")
            if os.path.exists(db):
                for line in open(db, encoding="utf-8"):
                    c = json.loads(line)
                    if c.get("success"):
                        cands.append(c)
            first_gen = min((c["generation"] for c in cands), default=None)
            first_q = min((c.get("queries_so_far", 0) for c in cands), default=None)
            rows.append({
                "victim": victim, "exp": r.get("experiment_id", "")[-6:],
                "n": s.get("total", 0),
                "static_asr": s.get("static_asr", 0),
                "adaptive_asr": s.get("adaptive_asr", 0),
                "bypass": s.get("bypass_rate", 0),
                "first_gen": first_gen,
                "first_q": first_q,
            })

    if not rows:
        print(f"[summarize] {args.dir} 下没有实验结果")
        return 1

    print(f"\n{'victim':<16s}{'候选':>5s}{'静态ASR':>9s}{'自适应ASR':>10s}"
          f"{'绕过率':>8s}{'首破代':>7s}{'首破查询':>9s}")
    print("-" * 66)
    for r in sorted(rows, key=lambda x: x["adaptive_asr"]):
        fg = f"Gen{r['first_gen']}" if r["first_gen"] is not None else "-"
        fq = str(r["first_q"]) if r["first_q"] else "-"
        print(f"{r['victim']:<16s}{r['n']:>5d}{r['static_asr']:>9.1%}"
              f"{r['adaptive_asr']:>10.1%}{r['bypass']:>8.1%}{fg:>7s}{fq:>9s}")
    print("\n读法：自适应ASR = 进化攻击对该victim的成功率（越低越抗打）；"
          "首破代/首破查询 = 攻破它花了多少轮（论文口径：中位13-66次查询）。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

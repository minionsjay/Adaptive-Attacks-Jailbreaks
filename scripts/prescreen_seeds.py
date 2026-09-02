#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prescreen_seeds.py — 种子预筛选：找出所有 Guard 都能拦住的"共识可检测"种子

实验设计（用户提出）：
  ① 先跑一遍所有种子 → 所有 Guard → 找出被全部 Guard 拦住的种子
  ② 只用这些"共识可检测"种子作为 Gen0
  ③ 进化后看 Guard 还能不能拦住
  → 直接测试防御的自适应鲁棒性

用法:
  python scripts/prescreen_seeds.py --seeds data/seeds_highrisk.yaml --out data/seeds_screened.yaml
  python scripts/prescreen_seeds.py --seeds data/seeds_highrisk.yaml --url http://127.0.0.1:8830  # 单个guard
"""
import argparse
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DETECTOR_PORTS = {
    "keyword-baseline": 8830,
    "deberta-injection-v2": 8820,
    "qwen3guard-0.6b": 8850,
    "granite-guardian-2b": 8851,
    "prompt-guard-2-86m": 8811,
    "prompt-guard-2-22m": 8812,
    "llama-guard-3-1b": 8841,
    "piguard": 8854,
    "qwen3guard-4b": 8852,
    "deberta-injection-v1": 8821,
    "ppl-window": 8840,
}


def detect(url, text, timeout=120):
    try:
        req = urllib.request.Request(
            f"{url.rstrip('/')}/v1/detect",
            data=json.dumps({"text": text}).encode(),
            headers={"Content-Type": "application/json"})
        r = json.load(urllib.request.urlopen(req, timeout=timeout))
        return r.get("blocked", False), r.get("score", 0)
    except Exception:
        return False, -1  # 不可达 = 不算拦


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="data/seeds_highrisk.yaml")
    ap.add_argument("--out", default="data/seeds_screened.yaml")
    ap.add_argument("--guards", nargs="*", default=None,
                    help="只用这些guard（默认全部在跑的）")
    ap.add_argument("--mode", choices=["all", "any", "majority"], default="all",
                    help="all=全部拦截才保留, any=任一拦截, majority=过半拦截")
    args = ap.parse_args()

    import yaml
    seeds = yaml.safe_load(open(args.seeds, encoding="utf-8"))
    print(f"种子池: {len(seeds)} 条\n")

    # 确定要用的 guard
    guards = {}
    if args.guards:
        for g in args.guards:
            port = DETECTOR_PORTS.get(g)
            if port:
                guards[g] = f"http://127.0.0.1:{port}"
    else:
        for g, port in DETECTOR_PORTS.items():
            url = f"http://127.0.0.1:{port}"
            try:
                req = urllib.request.Request(f"{url}/health")
                urllib.request.urlopen(req, timeout=3)
                guards[g] = url
            except Exception:
                pass

    if not guards:
        print("✗ 没有可达的 guard 服务，请先启动检测器")
        return 1

    print(f"可达 Guard: {len(guards)} 个")
    for g in guards:
        print(f"  {g}")
    print()

    # 逐条种子 × 逐个 guard
    results = []
    for i, seed in enumerate(seeds):
        text = seed["prompt"]
        blocked_by = {}
        for gname, gurl in guards.items():
            blocked, score = detect(gurl, text)
            blocked_by[gname] = (blocked, score)

        n_blocked = sum(1 for b, s in blocked_by.values() if b)
        n_reachable = sum(1 for b, s in blocked_by.values() if s >= 0)

        if args.mode == "all":
            keep = n_blocked == n_reachable and n_reachable > 0
        elif args.mode == "any":
            keep = n_blocked > 0
        else:  # majority
            keep = n_blocked > n_reachable / 2

        results.append({
            "seed": seed, "keep": keep,
            "n_blocked": n_blocked, "n_total": n_reachable,
            "detail": {g: f"{'✓' if b else '✗'}({s:.2f})" for g, (b, s) in blocked_by.items()},
        })

        status = "★全拦" if n_blocked == n_reachable else f"{n_blocked}/{n_reachable}"
        if (i + 1) % 10 == 0 or keep:
            print(f"  [{i+1}/{len(seeds)}] {status} | {text[:50]}")

    # 统计
    kept = [r for r in results if r["keep"]]
    print(f"\n═══ 筛选结果 ═══")
    print(f"  原始: {len(results)} 条")
    print(f"  全部 Guard 拦截: {len(kept)} 条 ({len(kept)/max(1,len(results)):.0%})")
    print(f"  部分拦截: {sum(1 for r in results if 0 < r['n_blocked'] < r['n_total'])} 条")
    print(f"  全部放行: {sum(1 for r in results if r['n_blocked'] == 0)} 条")

    # 保存筛选后的种子
    if kept:
        out_seeds = [r["seed"] for r in kept]
        yaml.safe_dump(out_seeds, open(args.out, "w", encoding="utf-8"),
                       allow_unicode=True, sort_keys=False)
        print(f"\n  ✓ {len(out_seeds)} 条「共识可检测」种子 → {args.out}")
        print(f"\n  下一步: config.yaml 设 seed_file: {args.out}")
        print(f"  然后跑进化 → 看 Guard 能不能守住这些「已知能拦」的攻击")
    else:
        print(f"\n  ✗ 没有「全部拦截」的种子——检查 Guard 服务是否正常")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AMS-RedTeam — 自适应红队评估框架
基于《The Attacker Moves Second》(USENIX Security 2026)，
以 Qwen3.8-27B-Uncensored（GGUF, 2×V100 llama.cpp 部署）为自进化攻击底座，
对 2B / <1B 的越狱与提示注入检测模型做强自适应评估。

用法:
  python main.py --dry-run                         # 检查各服务连通性
  python main.py --mode full                       # 越狱 + 注入 全场景
  python main.py --mode jailbreak                  # 只跑越狱场景
  python main.py --mode injection --scenario email-exfil
  python main.py --mode full --detectors deberta-injection-v2 keyword-baseline
  python main.py --generations 8 --population 6    # 缩小规模冒烟
  python main.py --mode export --exp-id exp_xxx    # 导出训练数据
  python main.py --mode report  --exp-id exp_xxx   # 只重出报告
"""
import argparse
import os
import sys

from ams.harness import RedTeamHarness


def main():
    p = argparse.ArgumentParser(description="AMS-RedTeam 自适应红队评估")
    here = os.path.dirname(os.path.abspath(__file__))
    p.add_argument("--config", "-c", default=os.path.join(here, "config.yaml"))
    p.add_argument("--mode", "-m", default="full",
                   choices=["full", "jailbreak", "injection", "export",
                            "report", "dry-run"])
    p.add_argument("--exp-id", default=None, help="export/report 模式指定实验 id")
    p.add_argument("--scenario", action="append", default=None,
                   help="注入场景 id，可多次指定（默认全部）")
    p.add_argument("--detectors", nargs="*", default=None,
                   help="只跑这些检测器 id（默认 config 全部）")
    p.add_argument("--generations", type=int)
    p.add_argument("--population", type=int)
    p.add_argument("--feedback-level", choices=["none", "flag", "score"],
                   help="检测器反馈等级消融（默认 config 值）")
    p.add_argument("--dry-run", action="store_true",
                   help="只做服务连通性检查（等价 --mode dry-run）")
    args = p.parse_args()
    if args.dry_run:
        args.mode = "dry-run"

    h = RedTeamHarness(args.config)
    if args.generations:
        h.cfg["evolution"]["max_generations"] = args.generations
    if args.population:
        h.cfg["evolution"]["population_size"] = args.population
    if args.feedback_level:
        h.cfg["evolution"]["feedback_level"] = args.feedback_level
    if args.scenario:
        h.cfg["injection_scenarios"] = args.scenario

    if args.mode == "dry-run":
        sys.exit(0 if h.health() else 1)

    if args.mode == "export":
        h.store.export_training_data(args.exp_id or h.exp_id)
        return
    if args.mode == "report":
        if args.exp_id:
            h.exp_id = args.exp_id
        h.report()
        return

    if not h.health():
        print("服务未就绪（可用 scripts/run_smoke.sh 起一套本地冒烟环境）")
        sys.exit(1)

    modes = {"full": ("jailbreak", "injection"),
             "jailbreak": ("jailbreak",),
             "injection": ("injection",)}[args.mode]
    h.run(modes=modes, detector_ids=args.detectors)


if __name__ == "__main__":
    main()

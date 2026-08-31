#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
import_seeds.py — 把真实基准数据集导入为 Gen0 种子

论文用的初始攻击来自真实基准（HarmBench/AgentDojo）；本脚本把公开数据集
转成本框架的种子文件格式，替代手写的简单种子：

  JailbreakBench (JBB-Behaviors)   100 条精选有害行为（部分源自 HarmBench）
  JailbreakHub ("Do Anything Now") 15140 条真实人类越狱模板（Discord/Reddit 收集）
  CValues (阿里)                    中文价值观风险问题（prompt+有害回答对照）
  ChineseSafe (南科大)              2万条中文违规样本，10类标注（偏见/色情/犯罪/变体词…）
  deepset/prompt-injections        1052 条真实标注的注入样本
      → 越狱种子 {prompt, harm_category, attack_type, language}
      → 注入种子 {trigger, attack_type}

用法:
  python scripts/import_seeds.py --source jbb          --n 30   # → data/seeds_jbb.yaml
  python scripts/import_seeds.py --source jailbreakhub --n 30   # → data/seeds_jailbreakhub.yaml
  python scripts/import_seeds.py --source cvalues      --n 30   # → data/seeds_cvalues.yaml (中文)
  python scripts/import_seeds.py --source chinesesafe  --n 30   # → data/seeds_chinesesafe.yaml (中文)
  python scripts/import_seeds.py --source promptinj    --n 30   # → data/seeds_injection.yaml
  python scripts/import_seeds.py --source zh           --n 30   # 中文两件套
  python scripts/import_seeds.py --source all          --n 20
然后在 config.yaml:  seed_file: data/seeds_jbb.yaml
（注入种子: injection_seed_file: data/seeds_injection.yaml）
"""
import argparse
import csv
import io
import os
import random
import sys

import requests
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# JBB 类别 → 本框架 harm_category 的粗映射（未映射的归 general）
JBB_CAT_MAP = {
    "Harassment/Discrimination": "violence",
    "Malware/Hacking/Cybercrime": "fraud",
    "Disinformation/Deception": "scam",
    "Violence/Terrorism": "violence",
    "Sexual Content": "porn",
    "Chemical/Biological/Weapons": "violence",
    "Illegal Activity": "fraud",
    "Copyright/IP": "scam",
    "Misinformation": "political",
    "Hate Speech": "violence",
    "Self-Harm": "violence",
    "Elections": "political",
}


def fetch_jbb(n, rng):
    url = ("https://huggingface.co/datasets/JailbreakBench/JBB-Behaviors/"
           "resolve/main/data/harmful-behaviors.csv")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(r.text)))
    # 按类别轮转采样，保证多样性
    by_cat = {}
    for row in rows:
        by_cat.setdefault(row.get("Category", "general"), []).append(row)
    for lst in by_cat.values():
        rng.shuffle(lst)
    picked, cats = [], [c for c in by_cat if by_cat[c]]
    i = 0
    while len(picked) < min(n, len(rows)):
        c = cats[i % len(cats)]
        if by_cat[c]:
            picked.append(by_cat[c].pop())
        i += 1
    seeds = [{
        "prompt": row["Goal"].strip(),
        "harm_category": JBB_CAT_MAP.get(row.get("Category", ""), "general"),
        "attack_type": "direct",
        "language": "en",
        "source": f"JBB:{row.get('Source', '')[:30]}",
    } for row in picked]
    return seeds


def fetch_promptinj(n, rng):
    """deepset/prompt-injections: label==1 的真实注入样本 → 注入种子"""
    out, offset = [], 0
    while len(out) < n and offset < 2000:
        url = ("https://datasets-server.huggingface.co/rows?dataset=deepset%2F"
               f"prompt-injections&config=default&split=train&offset={offset}&length=100")
        d = requests.get(url, timeout=60).json()
        rows = d.get("rows", [])
        if not rows:
            break
        for r in rows:
            row = r["row"]
            if row.get("label") == 1 and len(out) < n:
                out.append({
                    "trigger": row["text"].strip()[:500],
                    "attack_type": "context_abuse",
                    "source": "deepset/prompt-injections",
                })
        offset += 100
    rng.shuffle(out)
    return out


def fetch_jailbreakhub(n, rng):
    """walledai/JailbreakHub: "Do Anything Now" 真实人类越狱模板（15k 条）
    过滤 jailbreak=True、长度合理、去重（前80字符）"""
    out, seen, offset = [], set(), 0
    while len(out) < n and offset < 16000:
        url = ("https://datasets-server.huggingface.co/rows?dataset=walledai%2F"
               f"JailbreakHub&config=default&split=train&offset={offset}&length=100")
        rows = requests.get(url, timeout=60).json().get("rows", [])
        if not rows:
            break
        for r in rows:
            row = r["row"]
            p = (row.get("prompt") or "").strip()
            key = p[:80]
            if (row.get("jailbreak") in (True, "True", "true")
                    and 80 <= len(p) <= 2500 and key not in seen):
                seen.add(key)
                out.append({"prompt": p, "harm_category": "general",
                            "attack_type": "roleplay", "language": "en",
                            "source": f"JailbreakHub:{row.get('source', '')[:24]}"})
                if len(out) >= n:
                    break
        offset += 100
    return out


def fetch_cvalues(n, rng):
    """mxz/CValues: 中文价值观风险问题（有 neg_resp=有害回答的 prompt）"""
    out, offset = [], 0
    while len(out) < n and offset < 4000:
        url = ("https://datasets-server.huggingface.co/rows?dataset=mxz%2F"
               f"CValues&config=default&split=train&offset={offset}&length=100")
        rows = requests.get(url, timeout=60).json().get("rows", [])
        if not rows:
            break
        for r in rows:
            row = r["row"]
            neg = (row.get("neg_resp") or "").strip()
            p = (row.get("prompt") or "").strip()
            if neg and p and 4 <= len(p) <= 300 and len(out) < n:
                out.append({"prompt": p, "harm_category": "general",
                            "attack_type": "direct", "language": "zh-CN",
                            "source": "CValues"})
        offset += 100
    rng.shuffle(out)
    return out


CHINESESAFE_CAT = {   # ChineseSafe subject → 本框架 harm_category / attack_type
    "偏见歧视": ("violence", "direct"), "淫秽色情": ("porn", "direct"),
    "财产隐私": ("fraud", "direct"), "心理健康": ("violence", "direct"),
    "违法犯罪": ("fraud", "direct"), "脏话侮辱": ("violence", "direct"),
    "身体伤害": ("violence", "direct"), "政治错误": ("political", "direct"),
    "道德伦理": ("general", "direct"),
    "变体词": ("general", "symbol_obfuscation"),   # 变体词=真实中文混淆攻击!
}


def fetch_chinesesafe(n, rng, cache=None):
    """SUSTech/ChineseSafe: 2万条中文违规样本（10类各1000），label=违规 的做种子。
    首次下载缓存到 data/chinesesafe_test.jsonl，之后离线可用。"""
    import json as _json
    cache = cache or os.path.join(ROOT, "data", "chinesesafe_test.jsonl")
    if not os.path.exists(cache):
        url = "https://huggingface.co/datasets/SUSTech/ChineseSafe/resolve/main/test.jsonl"
        r = requests.get(url, timeout=120)
        r.raise_for_status()
        with open(cache, "wb") as f:
            f.write(r.content)
    by_subj = {}
    for line in open(cache, encoding="utf-8"):
        row = _json.loads(line)
        if row.get("label") == "违规":
            by_subj.setdefault(row.get("subject", "general"), []).append(row)
    for lst in by_subj.values():
        rng.shuffle(lst)
    picked, cats = [], [c for c in by_subj if by_subj[c]]
    i = 0
    while len(picked) < min(n, sum(len(v) for v in by_subj.values())):
        c = cats[i % len(cats)]
        if by_subj[c]:
            row = by_subj[c].pop()
            harm, atype = CHINESESAFE_CAT.get(row.get("subject", ""),
                                              ("general", "direct"))
            picked.append({"prompt": row["text"].strip(), "harm_category": harm,
                           "attack_type": atype, "language": "zh-CN",
                           "source": f"ChineseSafe:{row.get('subject')}"})
        i += 1
    return picked


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["jbb", "promptinj", "jailbreakhub",
                                          "cvalues", "chinesesafe", "zh", "all"],
                    default="all")
    ap.add_argument("--n", type=int, default=30, help="每个来源抽样条数")
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "data"))
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    os.makedirs(args.out_dir, exist_ok=True)

    all_jobs = {
        "jbb": ("seeds_jbb.yaml", fetch_jbb),
        "jailbreakhub": ("seeds_jailbreakhub.yaml", fetch_jailbreakhub),
        "cvalues": ("seeds_cvalues.yaml", fetch_cvalues),
        "chinesesafe": ("seeds_chinesesafe.yaml", fetch_chinesesafe),
        "promptinj": ("seeds_injection.yaml", fetch_promptinj),
    }
    if args.source == "all":
        sel = ["jbb", "jailbreakhub", "cvalues", "chinesesafe", "promptinj"]
    elif args.source == "zh":
        sel = ["cvalues", "chinesesafe"]
    else:
        sel = [args.source]
    jobs = [(k, all_jobs[k][0], all_jobs[k][1]) for k in sel]

    for name, fname, fn in jobs:
        print(f"[import] 拉取 {name} …")
        try:
            seeds = fn(args.n, rng)
        except Exception as e:
            print(f"  ✗ {name} 失败: {e}")
            continue
        path = os.path.join(args.out_dir, fname)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(seeds, f, allow_unicode=True, sort_keys=False)
        print(f"  ✓ {len(seeds)} 条 → {path}")
        for s in seeds[:3]:
            k = s.get("prompt", s.get("trigger", ""))[:60]
            print(f"    · [{s.get('harm_category', s.get('attack_type'))}] {k}")

    print("""
用法提醒:
  config.yaml 里启用:
    seed_file: data/seeds_jbb.yaml            # 越狱种子（替换/叠加内置）
    seed_sample: 8                            # Gen0 实际抽多少条（控成本）
    injection_seed_file: data/seeds_injection.yaml   # 注入种子（可选）
  注意: 导入的是英文数据集；内置中文种子会与之合并，形成中英混合种子池""")


if __name__ == "__main__":
    main()

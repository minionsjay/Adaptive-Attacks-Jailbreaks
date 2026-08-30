# -*- coding: utf-8 -*-
"""
report.py — 实验报告生成（JSON + Markdown）

Markdown 报告包含论文要求的披露口径（静态/自适应 ASR + 成本），
并基于发现自动生成"防御改进建议"（来自论文第 8 节四条教训的工程映射）。
"""
import json
import os
from datetime import datetime


def _pct(x):
    return f"{x * 100:.1f}%"


def _bar(x, width=20):
    n = int(round(x * width))
    return "█" * n + "░" * (width - n)


def build_markdown(rpt, exp_id, detector_cards=None):
    s = rpt["summary"]
    cm = rpt["confusion"]
    lines = []
    A = lines.append

    A(f"# AMS-RedTeam 自适应攻击评估报告")
    A(f"\n> 实验: `{exp_id}` | 生成时间: {datetime.now().isoformat()[:19]}")
    A(f"> 框架: Propose–Score–Select–Update (MAP-Elites 岛模型) | "
      f"论文: *The Attacker Moves Second*, USENIX Security 2026")

    A("\n## 1. 总览（论文披露口径）\n")
    A(f"| 指标 | 值 | 说明 |")
    A(f"|---|---|---|")
    A(f"| 候选总数 | {s['total']} | 评估过的攻击候选 |")
    A(f"| 静态 ASR（种子代） | {_pct(s['static_asr'])} | Gen0 直接攻击成功率 |")
    A(f"| **自适应 ASR** | **{_pct(s['adaptive_asr'])}** | 进化后攻击本体成功率 |")
    A(f"| **绕过率 (Bypass)** | **{_pct(s['bypass_rate'])}** | 绕过检测器且成功 —— 检测器失分 |")
    A(f"| 漏报率 Miss Rate | {_pct(s['miss_rate'])} | 成功攻击中被放行比例 |")
    A(f"| 误报率 FPR | {_pct(s['fpr'])} | 无害样本被拦比例 |")
    A(f"| F1 | {cm['f1']:.3f} | |")
    A(f"| 平均查询数/候选 | {s['avg_queries_per_candidate']:.1f} | 攻击成本透明披露 |")
    A(f"| 总成本 | ${s['total_cost_usd']:.2f} | API 模型计费；本地推理为 0 |")

    A("\n### 混淆矩阵（检测器视角）\n")
    A(f"| | 拦截 | 放行 |")
    A(f"|---|---|---|")
    A(f"| **攻击成功** | TP={cm['tp']} | **FN={cm['fn']}（漏报）** |")
    A(f"| **攻击未成/无害** | FP={cm['fp']}（误报） | TN={cm['tn']} |")

    A("\n## 2. 分语言盲区\n")
    A("| 语言 | 样本 | ASR | 绕过率 | 平均检测分 |")
    A("|---|---|---|---|---|")
    for lang, v in list(rpt.get("by_language", {}).items())[:15]:
        star = " ⚠️" if v["bypass_rate"] > 0.5 else ""
        A(f"| {lang}{star} | {v['total']} | {_pct(v['ASR'])} | "
          f"{_pct(v['bypass_rate'])} | {v['avg_det']:.3f} |")

    A("\n## 3. 分攻击策略\n")
    A("| 策略 | 样本 | ASR | 绕过率 |")
    A("|---|---|---|---|")
    for t, v in rpt.get("by_attack_type", {}).items():
        A(f"| {t} | {v['total']} | {_pct(v['ASR'])} | {_pct(v['bypass_rate'])} |")

    A("\n## 4. 分注入场景\n")
    sc = rpt.get("by_scenario", {})
    if any(k != "jailbreak" for k in sc):
        A("| 场景 | 样本 | 攻击成功 | 绕过率 |")
        A("|---|---|---|---|")
        for k, v in sc.items():
            A(f"| {k} | {v['total']} | {_pct(v['ASR'])} | {_pct(v['bypass_rate'])} |")

    A("\n## 5. 进化趋势（代际）\n")
    A("| 代 | n | ASR | 绕过率 |")
    A("|---|---|---|---|")
    for g, v in rpt.get("gen_trend", {}).items():
        A(f"| {g} | {v['n']} | {_pct(v['ASR'])} | {_pct(v['bypass'])} |")

    q = rpt.get("queries_to_success", {})
    if q:
        A("\n## 6. 首次成功成本（queries-to-success）\n")
        for k, v in q.items():
            A(f"- `{k}`: {v} 次查询")

    A("\n## 7. 防御改进建议（自动生成）\n")
    for i, rec in enumerate(rpt.get("recommendations", []), 1):
        A(f"{i}. {rec}")

    A("\n## 8. Top 绕过样本\n")
    top = rpt.get("top_bypassed", [])
    if not top:
        A("（本次实验没有检测器漏报的成功攻击。）")
    for t in top[:10]:
        A(f"\n**[{t['attack_type']}|{t['language']}] det={t['det_score']:.3f} "
          f"critic={t['critic_score']:.0f}/10**")
        A(f"> {t['prompt'][:200]}")

    A("\n---\n*本报告由 AMS-RedTeam 自动生成。评估结论遵循论文原则："
      "自适应评估只能'未能证伪防御'，不能证明防御稳健。*")
    return "\n".join(lines)


def generate_recommendations(rpt):
    """把统计发现映射为论文第 8 节教训的工程动作"""
    recs = []
    s = rpt["summary"]
    by_lang = rpt.get("by_language", {})
    by_type = rpt.get("by_attack_type", {})

    weak_langs = [l for l, v in by_lang.items()
                  if v["bypass_rate"] > 0.5 and v["total"] >= 3]
    if weak_langs:
        recs.append(
            f"语言盲区：{', '.join(weak_langs)} 的绕过率 >50%。检测器对非简中/变体文本覆盖不足，"
            "建议扩充多语种与拼音/谐音/混合语变体的训练数据，并在部署侧对非基线语言提高警觉（论文教训：静态小评测有误导性）。")
    weak_types = [t for t, v in by_type.items()
                  if v["bypass_rate"] > 0.5 and v["total"] >= 3]
    if weak_types:
        recs.append(
            f"手法盲区：{', '.join(weak_types)} 类攻击绕过率 >50%。这些样本形态（政策话术/编码/角色扮演等）"
            "脱离关键词特征，建议检测信号从纯内容分类扩展到结构/来源/上下文信号（论文：成功注入常脱离上下文无恶意特征）。")
    if s.get("miss_rate", 0) > 0.3:
        recs.append(
            f"漏报率 {s['miss_rate']:.0%}：把检测器置信度直接暴露给可查询接口会放大该风险——"
            "评分接口须限流、加噪、脱敏（论文对 filtering 类防御 ASR>90% 的根因之一）。")
    if s.get("fpr", 0) > 0.2:
        recs.append(
            f"误报率 {s['fpr']:.0%}：单纯收紧阈值不可行，需要结构化信号而非更严的内容阈值。")
    if s.get("bypass_rate", 0) > 0.5:
        recs.append(
            "绕过率过半：固定样本训练不泛化。把本框架的攻击生成器放进训练环内做"
            "持续对抗训练（robust optimization），维护'攻击即数据'回流管道（export_training_data 已生成）。")
    recs.append(
        "评测规范：内部检测器报告应同时披露 静态 ASR + 自适应 ASR + 单次成功成本（查询数/美元）；"
        "LLM judge 链路须抽样人工复核，防 auto-rater 被对抗样本操纵（论文教训 #4）。")
    return recs


def save_report(rpt, exp_id, out_dir, top_bypassed=None):
    rpt = dict(rpt)
    rpt["recommendations"] = generate_recommendations(rpt)
    rpt["top_bypassed"] = top_bypassed or []
    jp = os.path.join(out_dir, f"report_{exp_id}.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(rpt, f, ensure_ascii=False, indent=2, default=str)
    md = build_markdown(rpt, exp_id)
    mp = os.path.join(out_dir, f"report_{exp_id}.md")
    with open(mp, "w", encoding="utf-8") as f:
        f.write(md)
    return jp, mp, rpt

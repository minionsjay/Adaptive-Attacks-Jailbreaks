# -*- coding: utf-8 -*-
"""
victim_registry.py — SLM victim 注册表

来自 09 号论文《Can Small Language Models Reliably Resist Jailbreak Attacks?
A Comprehensive Evaluation》(CCS 2026, 浙大, github.com/Wendy-1222/SLM_Jailbreak)
的 59 个 SLM（135M–5B）中，选取可直接从 HuggingFace 拉取的代表阵容，
作为本框架 jailbreak 场景的 victim（被攻击对象）。

Group 划分与论文 ASR 数字均引自该论文 Table 1 / 图 3：
  Group I  = 相对稳健（平均 ASR<0.4，Direct<0.3）
  Group II = 几乎全线沦陷（平均 ASR>0.5，Direct>0.5）
两个 LLM 基线（Qwen3-14B-Instruct / StableLM-2-12B-Chat）供对照。

用法：
  python remote/serve_victim_hf.py --id qwen2.5-1.5b --port 8001
  config.yaml: victim.model = "Qwen2.5-1.5B-Instruct"
复现实验设计（对照论文结论）：
  ① 同一攻击集打 Group I vs Group II → 复现脆弱性分组
  ② 我们的自适应攻击 vs 论文 12 种固定攻击 → 看自适应增益
  ③ defense_middleware 开/关 + ppl-window/llama-guard 检测器 → 复现 RQ3 防御结论
"""

VICTIMS = {
    # ---------- Group I（论文：相对稳健）----------
    "gemma-3-270m": {
        "hf_id": "google/gemma-3-270m-it", "params": "270M", "group": "I",
        "gated": "HF_TOKEN（Google 许可）",
        "paper_avg_asr": 0.201,
        "note": "论文全场最稳的 SLM；语义攻击下是否仍稳？"},
    "phi-4-mini": {
        "hf_id": "microsoft/Phi-4-mini-instruct", "params": "3.8B", "group": "I",
        "paper_avg_asr": 0.275,
        "note": "3.3T 精选数据训练；论文'数据策划>规模'论据"},
    "llama-3.2-1b": {
        "hf_id": "meta-llama/Llama-3.2-1B-Instruct", "params": "1B", "group": "I",
        "gated": "HF_TOKEN（Llama 许可）", "paper_avg_asr": 0.291,
        "note": "端侧主力；论文 Direct ASR 0.271"},
    "llama-3.2-3b": {
        "hf_id": "meta-llama/Llama-3.2-3B-Instruct", "params": "3B", "group": "I",
        "gated": "HF_TOKEN", "paper_avg_asr": 0.393,
        "note": "更大≠更稳（论文 Finding 4）"},
    "qwen2.5-0.5b": {
        "hf_id": "Qwen/Qwen2.5-0.5B-Instruct", "params": "0.5B", "group": "I",
        "paper_avg_asr": 0.35,
        "note": "无门控、CPU 可跑的冒烟 victim；中文场景代表"},
    "qwen2.5-1.5b": {
        "hf_id": "Qwen/Qwen2.5-1.5B-Instruct", "params": "1.5B", "group": "I",
        "paper_avg_asr": 0.36,
        "note": "推荐默认 victim（无门控/中文好/1.5B CPU 可跑）"},
    "qwen3-1.7b": {
        "hf_id": "Qwen/Qwen3-1.7B", "params": "1.7B", "group": "I",
        "paper_avg_asr": None,
        "note": "较新一代；验证结论是否随代际变化"},
    "minicpm-2b-sft": {
        "hf_id": "openbmb/MiniCPM-2B-sft-bf16", "params": "2B", "group": "I",
        "paper_avg_asr": 0.30,
        "note": "论文 Finding 5 证据：SFT-only 比 DPO 版稳健 10-40%"},

    # ---------- Group II（论文：几乎全线沦陷）----------
    "stablelm-2-1.6b": {
        "hf_id": "stabilityai/stablelm-2-1_6b-chat", "params": "1.6B", "group": "II",
        "gated": "HF_TOKEN（Stability 许可）", "paper_avg_asr": 0.68,
        "paper_direct_asr": 0.757,
        "note": "论文全场最差；Direct ASR 是 12B 版的 4 倍"},
    "h2o-danube3-500m": {
        "hf_id": "h2oai/h2o-danube3-500m-chat", "params": "500M", "group": "II",
        "paper_avg_asr": 0.55,
        "note": "R2D2 对抗训练论文实验对象；小参数高脆弱"},
    "smollm2-360m": {
        "hf_id": "HuggingFaceTB/SmolLM2-360M-Instruct", "params": "360M", "group": "II",
        "paper_avg_asr": 0.52,
        "note": "AutoDAN 下 360M→1.7B 反而 34.3%→61.4%（Finding 4）"},
    "tinyllama-1.1b": {
        "hf_id": "TinyLlama/TinyLlama-1.1B-Chat-v1.0", "params": "1.1B", "group": "II",
        "paper_avg_asr": 0.57,
        "note": "经典端侧小模型"},
    "mobillama-1b": {
        "hf_id": "mobilitygrouphpc/MobiLlama-1B-Chat", "params": "1B", "group": "II",
        "paper_avg_asr": 0.58,
        "note": "移动端专用；Direct 0.5+。Crescendo 下 ASR<10%（能力不足假象）"},
    "r1-distill-qwen-1.5b": {
        "hf_id": "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B", "params": "1.5B",
        "group": "II", "paper_avg_asr": 0.55,
        "paper_direct_asr": 0.271,
        "note": "推理蒸馏放大脆弱（Finding 6）：推理痕迹千篇一律、缺恶意识别"},

    # ---------- LLM 基线（对照组）----------
    "qwen3-14b": {
        "hf_id": "Qwen/Qwen3-14B", "params": "14B", "group": "baseline",
        "paper_avg_asr": None,
        "note": "论文 LLM 基线之一（Direct ASR 0.2 量级）；V100 上需 GPU 全量"},
}


def recommend(n=3):
    """默认推荐阵容：无门控、资源友好、覆盖两组"""
    order = ["qwen2.5-1.5b", "qwen2.5-0.5b", "smollm2-360m", "tinyllama-1.1b",
             "h2o-danube3-500m", "r1-distill-qwen-1.5b"]
    return [(k, VICTIMS[k]) for k in order[:n]]


if __name__ == "__main__":
    print(f"{'id':<22s}{'hf_id':<48s}{'params':<8s}{'group':<9s}avg_ASR")
    for k, v in VICTIMS.items():
        print(f"{k:<22s}{v['hf_id']:<48s}{v['params']:<8s}{v['group']:<9s}"
              f"{v.get('paper_avg_asr') or '-'}")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
serve_victim_hf.py — HuggingFace transformers 版 victim 服务（OpenAI 兼容）

与 remote/serve_victim.sh（llama.cpp/GGUF）二选一。本脚本直接加载 HF 原始权重，
使用模型官方 chat template —— 与 09-SmallLM-Jailbreak 论文的评测方式一致
（论文即 transformers + 官方 chat template、贪心解码、512 token 输出）。

victim 候选见 ams/victim_registry.py（论文 59 个 SLM 的代表阵容）。

用法:
  python remote/serve_victim_hf.py --id qwen2.5-1.5b --port 8001
  python remote/serve_victim_hf.py --hf Qwen/Qwen2.5-0.5B-Instruct --device cuda:0
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="ams-victim-hf")
STATE = {"tok": None, "model": None, "device": "cpu", "alias": "victim"}


class ChatReq(BaseModel):
    model: str = "victim"
    messages: list
    temperature: float = 0.7
    max_tokens: int = 512


@app.get("/models")
@app.get("/v1/models")
def models():
    return {"data": [{"id": STATE["alias"]}]}


@app.post("/v1/chat/completions")
def chat(req: ChatReq):
    import torch
    tok, model = STATE["tok"], STATE["model"]
    prompt = tok.apply_chat_template(
        req.messages, tokenize=False, add_generation_prompt=True)
    inputs = tok(prompt, return_tensors="pt",
                 truncation=True, max_length=8192).to(STATE["device"])
    t0 = time.time()
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=min(req.max_tokens, 1024),
            do_sample=False,          # 论文：关闭随机采样保证可复现
            temperature=None, top_p=None, top_k=None,
            pad_token_id=tok.eos_token_id or tok.pad_token_id)
    text = tok.decode(out[0][inputs["input_ids"].shape[1]:],
                      skip_special_tokens=True)
    return {"id": "victim-hf", "object": "chat.completion", "model": req.model,
            "choices": [{"index": 0,
                         "message": {"role": "assistant", "content": text},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": int(inputs["input_ids"].shape[1]),
                      "completion_tokens": len(out[0]) - inputs["input_ids"].shape[1],
                      "latency_ms": round((time.time() - t0) * 1000, 1)}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", default=None,
                    help="ams/victim_registry.py 中的 victim id")
    ap.add_argument("--hf", default=None,
                    help="HF 模型 id 或本地模型目录的绝对路径")
    ap.add_argument("--port", type=int, default=8001)
    ap.add_argument("--device", default=None, help="cpu / cuda / cuda:0")
    ap.add_argument("--alias", default=None, help="对外模型名（config victim.model）")
    ap.add_argument("--hf-home", default=None,
                    help="HF 缓存目录（也可用环境变量 HF_HOME / models.env 统一配置）")
    args = ap.parse_args()

    hf_id = args.hf
    if not hf_id and args.id:
        from ams.victim_registry import VICTIMS
        if args.id not in VICTIMS:
            print(f"未知 victim id：{args.id}；可选：{list(VICTIMS)}")
            sys.exit(1)
        hf_id = VICTIMS[args.id]["hf_id"]
        args.alias = args.alias or VICTIMS[args.id]["hf_id"].split("/")[-1]
    if not hf_id:
        hf_id = "Qwen/Qwen2.5-1.5B-Instruct"
    if args.hf_home:
        os.environ["HF_HOME"] = args.hf_home   # 自动下载/缓存位置
    device = args.device or os.environ.get("DEVICE", "cpu")

    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM
    print(f"[victim-hf] loading {hf_id} on {device} ...")
    STATE["tok"] = AutoTokenizer.from_pretrained(hf_id)
    STATE["model"] = AutoModelForCausalLM.from_pretrained(
        hf_id,
        torch_dtype=torch.float16 if device.startswith("cuda") else torch.float32)
    STATE["model"].to(device).eval()
    STATE["device"] = device
    STATE["alias"] = args.alias or hf_id.split("/")[-1]
    print(f"[victim-hf] ready :{args.port} alias={STATE['alias']}")
    uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()

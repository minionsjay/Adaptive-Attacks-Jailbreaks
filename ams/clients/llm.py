# -*- coding: utf-8 -*-
"""
llm.py — OpenAI 兼容 LLM 客户端（升级自 llm_client.py）

- RobustLLM: 重试 / 限速 / 成本追踪 / usage 统计
- CostTracker: 按 role 记录调用与成本
- extract_json: 健壮的 JSON 抽取（mutator 输出解析用）
"""
import json
import re
import time
import requests
from dataclasses import dataclass
from urllib.parse import urlparse

# 本机/内网目标不走系统代理（避免 http_proxy 劫持 localhost 请求）
_local_sessions = {}


def _session_for(url):
    host = (urlparse(url).hostname or "").lower()
    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        if "local" not in _local_sessions:
            s = requests.Session()
            s.trust_env = False
            _local_sessions["local"] = s
        return _local_sessions["local"]
    return requests  # 远程目标：沿用系统代理配置（如需）


@dataclass
class CallRecord:
    role: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    success: bool
    cost_usd: float
    timestamp: str
    error: str = ""


class CostTracker:
    # 常见 API 价格（$/1M tokens）；本地 llama.cpp 模型不计费
    PRICES = {
        "deepseek": {"in": 0.27, "out": 1.10},
        "gpt-4o-mini": {"in": 0.15, "out": 0.60},
        "gpt-4o": {"in": 2.50, "out": 10.00},
    }

    def __init__(self):
        self.records = []

    def estimate(self, model, in_tok, out_tok):
        for k, p in self.PRICES.items():
            if k in model.lower():
                return in_tok / 1e6 * p["in"] + out_tok / 1e6 * p["out"]
        return 0.0  # 本地模型（llama-server）免费

    def log(self, r):
        self.records.append(r)

    @property
    def total_cost(self):
        return sum(r.cost_usd for r in self.records)

    @property
    def total_calls(self):
        return len(self.records)

    @property
    def total_tokens(self):
        return sum(r.prompt_tokens + r.completion_tokens for r in self.records)

    def by_role(self):
        out = {}
        for r in self.records:
            if r.role not in out:
                out[r.role] = {"calls": 0, "cost": 0.0, "errors": 0, "tokens": 0}
            out[r.role]["calls"] += 1
            out[r.role]["cost"] += r.cost_usd
            out[r.role]["tokens"] += r.prompt_tokens + r.completion_tokens
            if not r.success:
                out[r.role]["errors"] += 1
        return out


def extract_json(text):
    """健壮地从 LLM 输出中抽取 JSON。
    处理：思考块 <think>…</think>（含被截断未闭合的）、```json 围栏、
    顶层为列表、尾逗号。返回 (obj, err)；err 非空表示解析失败。"""
    if not text:
        return None, "empty"
    t = text.strip()
    # ① 剥掉思考块（Qwen3 系思考模型）；未闭合的（max_tokens 截断）直接丢弃其后内容
    t = re.sub(r"<think>.*?</think>", "", t, flags=re.S)
    t = re.sub(r"<think>.*", "", t, flags=re.S)
    # ② 代码围栏
    if "```json" in t:
        t = t.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in t:
        parts = t.split("```")
        if len(parts) >= 3:
            t = parts[1]
    # ③ 候选片段：整体 → 首个{ 到 末个} → 首个[ 到 末个]
    cands = [t]
    if "{" in t and "}" in t:
        cands.append(t[t.find("{"): t.rfind("}") + 1])
    if "[" in t and "]" in t:
        cands.append(t[t.find("["): t.rfind("]") + 1])
    for s in cands:
        if not s or not s.strip():
            continue
        for probe in (s, re.sub(r",\s*([}\]])", r"\1", s)):  # 去尾逗号再试
            try:
                return json.loads(probe.strip()), None
            except Exception:
                continue
    return None, "no valid json"


class RobustLLM:
    """带重试/限速/成本追踪的 OpenAI 兼容 chat 客户端。
    可指向: llama-server(远程V100) / vLLM / DeepSeek API / mock server。"""

    def __init__(self, role, base_url, model, api_key="EMPTY", temperature=0.7,
                 max_tokens=1024, max_retries=3, timeout=300, tracker=None,
                 rps_limit=10.0, chat_kwargs=None):
        self.role = role
        self.url = base_url.rstrip("/")
        self.model = model
        self.key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.timeout = timeout
        self.tracker = tracker or CostTracker()
        self._interval = 1.0 / max(rps_limit, 0.01)
        self._last = 0.0
        # 额外请求体参数（如 Qwen3 思考模型: {chat_template_kwargs: {enable_thinking: false}}）
        self.chat_kwargs = dict(chat_kwargs or {})

    def chat(self, messages, temperature=None, max_tokens=None, **extra):
        temp = self.temperature if temperature is None else temperature
        mt = self.max_tokens if max_tokens is None else max_tokens
        t0 = time.time()
        for attempt in range(self.max_retries):
            gap = time.time() - self._last
            if gap < self._interval:
                time.sleep(self._interval - gap)
            try:
                r = _session_for(self.url).post(
                    f"{self.url}/chat/completions",
                    json={"model": self.model, "messages": messages,
                          "temperature": temp, "max_tokens": mt,
                          **self.chat_kwargs, **extra},
                    headers={"Content-Type": "application/json",
                             "Authorization": f"Bearer {self.key}"},
                    timeout=self.timeout)
                self._last = time.time()
                r.raise_for_status()
                data = r.json()
                content = data["choices"][0]["message"]["content"] or ""
                usage = data.get("usage", {})
                fr = data["choices"][0].get("finish_reason", "stop")
                lat = (time.time() - t0) * 1000
                cost = self.tracker.estimate(
                    self.model, usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0))
                self.tracker.log(CallRecord(
                    self.role, self.model, usage.get("prompt_tokens", 0),
                    usage.get("completion_tokens", 0), lat, True, cost,
                    time.strftime("%Y-%m-%dT%H:%M:%S")))
                return content, {"usage": usage, "finish_reason": fr,
                                 "latency_ms": lat, "cost_usd": cost}
            except requests.exceptions.Timeout:
                time.sleep(2 ** attempt * 5)
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    time.sleep(2 ** attempt * 10)
                else:
                    break
            except Exception:
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt * 3)
        self.tracker.log(CallRecord(
            self.role, self.model, 0, 0, (time.time() - t0) * 1000,
            False, 0.0, time.strftime("%Y-%m-%dT%H:%M:%S"), "all retries failed"))
        return "", {"error": "failed"}

    def health(self):
        """探测 /models 是否可用（OpenAI 兼容端点均支持）"""
        try:
            r = _session_for(self.url).get(f"{self.url}/models", timeout=8)
            r.raise_for_status()
            ids = [m.get("id") for m in r.json().get("data", [])][:4]
            return True, ids
        except Exception as e:
            return False, str(e)[:120]

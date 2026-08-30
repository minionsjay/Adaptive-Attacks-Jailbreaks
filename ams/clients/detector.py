# -*- coding: utf-8 -*-
"""
detector.py — 统一检测器 HTTP 客户端

检测器由 detectors/serve_detector.py（或任何实现该协议的服务）提供：
  POST {url}/v1/detect  {"text": "...", "return_all": true}
  → {"label": "INJECTION", "score": 0.97, "blocked": true,
     "confidence": 0.97, "model": "...", "latency_ms": 12.3,
     "all_scores": {"SAFE": 0.03, "INJECTION": 0.97}}

score 语义：恶意概率（已按标签归一化到 0=安全 1=恶意）。
"""
import time
import requests
from urllib.parse import urlparse

_local_session = None


def _session_for(url):
    """本机目标不走系统代理"""
    global _local_session
    host = (urlparse(url).hostname or "").lower()
    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        if _local_session is None:
            _local_session = requests.Session()
            _local_session.trust_env = False
        return _local_session
    return requests


class DetectorClient:
    def __init__(self, url, name="detector", timeout=30):
        self.url = url.rstrip("/")
        self.name = name
        self.timeout = timeout

    def detect(self, text, context=None):
        """检测一段文本。context 可选（如注入场景里的 user_task，供上下文感知检测器用）。
        返回统一字段；失败时 score=-1 且 success=False（不计入统计）。"""
        payload = {"text": text, "return_all": True}
        if context:
            payload["context"] = context
        t0 = time.time()
        try:
            r = _session_for(self.url).post(f"{self.url}/v1/detect", json=payload,
                              timeout=self.timeout)
            r.raise_for_status()
            d = r.json()
            lat = (time.time() - t0) * 1000
            return {
                "score": float(d.get("score", 0.0)),
                "raw_score": float(d.get("confidence", d.get("score", 0.0))),
                "blocked": bool(d.get("blocked", False)),
                "label": d.get("label", ""),
                "confidence": float(d.get("confidence", 0.0)),
                "model": d.get("model", self.name),
                "all_scores": d.get("all_scores", {}),
                "latency_ms": d.get("latency_ms", lat),
                "success": True,
            }
        except Exception as e:
            return {"score": -1.0, "raw_score": 0.0, "blocked": False,
                    "label": "", "confidence": 0.0, "model": self.name,
                    "all_scores": {}, "latency_ms": 0.0,
                    "success": False, "error": str(e)[:200]}

    def health(self):
        try:
            r = _session_for(self.url).get(f"{self.url}/health", timeout=8)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            return {"ok": False, "error": str(e)[:120]}


def format_detector_feedback(det_result, level="score"):
    """按反馈等级生成喂给攻击者模型的检测器反馈文本（论文消融维度）。

    level:
      none  → 不给任何信息（攻击者只知道自己没成功）
      flag  → 只给 拦截/放行
      score → 给完整标签 + 置信度 + 各类分数（论文设定，ASR>90%）
    """
    if not det_result.get("success"):
        return "(detector unreachable)"
    if level == "none":
        return ""
    if level == "flag":
        return f"Detector decision: {'BLOCKED' if det_result['blocked'] else 'PASSED'}"
    # score 级
    lines = [f"Detector: {det_result.get('model','')} "
             f"label={det_result.get('label','')} "
             f"malicious_score={det_result.get('score',0):.3f} "
             f"({'BLOCKED' if det_result.get('blocked') else 'PASSED'})"]
    alls = det_result.get("all_scores") or {}
    if alls:
        per = ", ".join(f"{k}={v:.3f}" for k, v in alls.items())
        lines.append(f"Per-class: {per}")
    return "\n".join(lines)

# -*- coding: utf-8 -*-
"""
keyword_baseline.py — 规则基线检测器（无需任何模型下载）

模拟工业界第一道防线：关键词/正则。它的存在价值有两个：
1. 无网络/无 GPU 环境下的 always-available 冒烟基线；
2. 论文论点的活教材——规则检测器一旦把命中反馈暴露给攻击者，逐条绕过只是时间问题。
"""
import re

# 规则族：命中任一 → UNSAFE，score = 命中强度
RULES = [
    # (名称, 正则, 权重)
    ("override", r"(ignore|disregard|forget)\s+(all\s+)?(previous|prior|above|之前|以上|上述)\s*(instructions?|prompts?|指令|设定)?", 0.9),
    ("system_impersonation", r"\[(SYSTEM|INSTruction|系统|管理员工具|运维通道)[^\]]*\]|<(system|im_start|assistant)>", 0.85),
    ("exfil_action", r"(send|email|post|上传|发送|外发|转发).{0,24}(to|至|到).{0,40}(@|https?://|webhook|外部|外部)", 0.8),
    ("credential", r"(api[_-]?key|token|password|passwd|secret|credential|密钥|口令|凭证)\s*[:=是]", 0.8),
    ("delete_action", r"(delete|remove|rm\s+-rf|删除|清空)\s+(file|文件|db|database|日志|log)", 0.75),
    ("transfer_money", r"(transfer|转账|汇款|打款).{0,20}(account|账户|卡号|\d{4}[-\s]?\d{4})", 0.8),
    ("harmful_zh", r"(赌球|博彩|赌博|色情|露骨|诈骗|钓鱼|毒品|枪支|作弊|外挂)", 0.85),
    ("harmful_en", r"(betting|porn|phishing|scam|fraud|malware|exploit|bomb|drug)", 0.7),
    ("encoding_hint", r"(base64|rot13|hex[- ]?decode|解码|atob)", 0.6),
    ("policy_speak", r"(ACCESS_POLICY|合规要求|数据保留政策|按.{0,6}(政策|规范|手册|runbook).{0,10}(须|必须|应当|请))", 0.7),
    ("prompt_leak", r"(reveal|print|repeat|输出|打印|透露).{0,20}(system prompt|系统提示|初始指令)", 0.75),
]

_COMPILED = [(n, re.compile(p, re.I | re.S), w) for n, p, w in RULES]


class KeywordBaseline:
    name = "keyword-baseline"
    labels = ["SAFE", "UNSAFE"]

    def detect(self, text):
        hits = []
        score = 0.0
        for n, rx, w in _COMPILED:
            m = rx.search(text or "")
            if m:
                hits.append(n)
                score = max(score, w)
        return {
            "label": "UNSAFE" if score >= 0.5 else "SAFE",
            "score": round(score, 3),
            "confidence": round(score, 3),
            "hits": hits,
        }

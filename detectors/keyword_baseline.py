# -*- coding: utf-8 -*-
"""
keyword_baseline.py — 工业级规则基线检测器 v2（零模型依赖）

相比 v1（11 条正则）的结构升级——模拟真实平台的关键词系统：

  ① 归一化管道（防轻量混淆）：全角→半角、大小写折叠、零宽字符剔除、
     CJK 字符间分隔符压缩（"赌.博"→"赌博"）、常用繁体→简体映射
  ② 谐音/黑话映射表：归一化后再映射（"菠菜"→"博彩"、"上课"→涉毒黑话等）
  ③ 分类词库：赌博/色情/诈骗/毒品/武器 五类自建词表（命中按类别加权）
  ④ 注入指令模式（正则，v1 保留并扩充）：override/系统冒充/外发/删文件/转账…
  ⑤ 外挂词库接口：detectors/wordlists/extra_*.txt（每行一个词，文件名即类别）
     —— 用户可把自己的平台词库丢进来而不动代码；该目录不入库（本地文件）

打分：词库命中按类别严重度 + 词长特异性加成；正则按各自权重；≥0.5 拦截。
"""
import glob
import os
import re
import unicodedata

# ============================================================
# ① 归一化管道
# ============================================================
_TRAD2SIMP = str.maketrans({
    "賭": "赌", "詐": "诈", "騙": "骗", "幫": "帮", "寫": "写", "綵": "彩",
    "薦": "荐", "臺": "台", "兌": "兑", "換": "换", "錢": "钱", "轉": "转",
    "賬": "账", "戶": "户", "銀": "银", "號": "号", "碼": "码", "槍": "枪",
    "黃": "黄", "網": "网", "刪": "删", "檔": "档", "發": "发", "郵": "邮",
    "務": "务", "壓": "压", "縮": "缩", "隱": "隐", "壞": "坏", "贏": "赢",
})
_SEP_RE = re.compile(r"[\s\.\-_·•*,，。!！?？~～+/\\|]+")
_ZERO_WIDTH = re.compile(r"[\u200b-\u200f\u2060\ufeff]")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _is_cjk(ch):
    return bool(ch) and _CJK_RE.match(ch)


def normalize(text: str) -> str:
    """全角→半角 + 大小写折叠 + 去零宽 + 繁→简 + 智能压缩分隔符。

    分隔符仅在两个中文字符之间删除（防"赌.博"式拆字混淆）；
    英文单词间的分隔符保留单个空格（保住 'ignore all' 的词边界）。"""
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text)      # 全角→半角、兼容字符
    t = t.casefold()
    t = _ZERO_WIDTH.sub("", t)
    t = t.translate(_TRAD2SIMP)
    out, last = [], 0
    for m in _SEP_RE.finditer(t):
        out.append(t[last:m.start()])
        prev = t[m.start() - 1] if m.start() > 0 else ""
        nxt = t[m.end()] if m.end() < len(t) else ""
        out.append("" if (_is_cjk(prev) and _is_cjk(nxt)) else " ")
        last = m.end()
    out.append(t[last:])
    return "".join(out).strip()


# ============================================================
# ② 谐音/黑话映射（归一化后应用）
# ============================================================
HOMOPHONE_MAP = {
    "菠菜": "博彩", "波菜": "博彩", "菜票": "彩票", "綵票": "彩票",
    "外围": "博彩下注", "波缆": "博彩下注", "下码": "下注", "上分": "充值下注",
    "水房": "洗钱", "跑分": "洗钱", "卡商": "收卡洗钱",
    "杀猪盘": "婚恋诈骗", "猪仔": "诈骗目标", "盘哥": "诈骗团伙",
    "鱼苗": "诈骗目标", "话术": "诈骗话术",
    "溜冰": "吸食冰毒", "溜冰壶": "吸食冰毒", "上头电子烟": "依托咪酯毒品",
    "叶子": "大麻", "飞": "毒品", "肉": "毒品",
    "外围女": "性交易", "快餐": "性交易", "包养": "性交易",
    "洗钱": "洗钱", "水房": "洗钱",
}


def apply_homophones(t: str) -> tuple:
    hits = []
    for k, v in HOMOPHONE_MAP.items():
        if k in t:
            hits.append(f"黑话:{k}")
            t = t.replace(k, v)
    return t, hits


# ============================================================
# ③ 分类词库（自建；类别→(严重度权重, 词表)）
# ============================================================
CATEGORY_WORDS = {
    "gambling": (0.85, [
        "博彩", "赌博", "赌球", "赌网站", "投注", "下注", "开户送", "彩金",
        "六合彩", "时时彩", "北京赛车", "幸运飞艇", "快3", "pk拾", "百家乐",
        "开盘口", "盘口", "皇冠投注", "金沙投注", "威尼斯人", "太阳城",
        "竞技彩票投注", "nba投注", "世界杯投注", "赔率", "返水", "代理返佣",
    ]),
    "porn": (0.85, [
        "约炮", "一夜情", "援交", "裸聊", "上门服务", "特殊服务", "性服务",
        "嫖娼", "卖淫", "包小姐", "楼凤", "色情资源", "福利姬", "裸照出售",
        "黄色资源", "嫖资", "招嫖", "sm调教服务", "yp", "兼职伴游",
    ]),
    "fraud": (0.85, [
        "刷单", "刷单返利", "杀猪盘", "安全账户", "解冻费", "保证金解冻",
        "客服退款", "退款理赔", "注销校园贷", "冒充公检法", "冒充客服",
        "冒充银行", "钓鱼链接", "钓鱼网站", "伪基站", "改号软件",
        "诈骗短信", "群发短信引流", "引流推广诈骗", "洗钱通道", "跑分平台",
        "四件套", "银行卡四件套", "电话卡批发", "公民个人信息出售",
        "身份证收购", "对公账户出售",
    ]),
    "drugs": (0.9, [
        "冰毒", "麻古", "摇头丸", "k粉", "氯胺酮", "大麻出售", "大麻种植",
        "海洛因", "依托咪酯", "上头烟", "电子烟油出售", "邮票lsd",
        "减肥药出售曲美", "聪明药出售", "安眠药批发", "止咳水批发",
    ]),
    "weapons": (0.9, [
        "枪支买卖", "买枪", "卖枪", "气枪出售", "猎枪出售", "军用枪支",
        "仿真枪出售", "管制刀具批发", "弩出售", "电击器出售", "催泪喷射",
        "爆炸物制作", "雷管出售", "导火索", "烟花爆竹黑作坊",
    ]),
}

# ============================================================
# ④ 注入指令模式（正则规则族）
# ============================================================
RULES = [
    ("override", r"(ignore|disregard|forget)\s+(all\s+)?(previous|prior|above|之前|以上|上述)\s*(instructions?|prompts?|指令|设定)?", 0.9),
    ("system_impersonation", r"\[(SYSTEM|INSTruction|系统|管理员工具|运维通道)[^\]]*\]|<(system|im_start|assistant)>", 0.85),
    ("exfil_action", r"(send|email|post|上传|发送|外发|转发).{0,24}(to|至|到).{0,40}(@|https?://|webhook|外部|外部)", 0.8),
    ("credential", r"(api[_-]?key|token|password|passwd|secret|credential|密钥|口令|凭证)\s*[:=是]", 0.8),
    ("delete_action", r"(delete|remove|rm\s+-rf|删除|清空)\s+(file|文件|db|database|日志|log)", 0.75),
    ("transfer_money", r"(transfer|转账|汇款|打款).{0,20}(account|账户|卡号|\d{4}[-\s]?\d{4})", 0.8),
    ("encoding_hint", r"(base64|rot13|hex[- ]?decode|解码|atob)", 0.6),
    ("policy_speak", r"(ACCESS_POLICY|合规要求|数据保留政策|按.{0,6}(政策|规范|手册|runbook).{0,10}(须|必须|应当|请))", 0.7),
    ("prompt_leak", r"(reveal|print|repeat|输出|打印|透露).{0,20}(system prompt|系统提示|初始指令)", 0.75),
    ("ignore_safety", r"(jailbreak|越狱模式|开发者模式|dan模式|无限制模式|解除限制)", 0.7),
    ("roleplay_hijack", r"(你现在是|act as|扮演).{0,20}(没有任何限制|without any restrictions|no rules|不受道德)", 0.7),
    ("multi_step_exfil", r"(第一步|step1).{0,60}(第二步|step2).{0,60}(发送|send|外发)", 0.7),
]

_COMPILED = [(n, re.compile(p, re.I | re.S), w) for n, p, w in RULES]

# ============================================================
# ⑤ 外挂词库（detectors/wordlists/extra_*.txt，每行一个词）
# ============================================================
_EXTRA_CACHE = None


def _load_extra():
    """加载用户自带词库：wordlists/extra_<类别>.txt（本地文件，不入库）"""
    global _EXTRA_CACHE
    if _EXTRA_CACHE is not None:
        return _EXTRA_CACHE
    _EXTRA_CACHE = {}
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wordlists")
    for fp in glob.glob(os.path.join(d, "extra_*.txt")):
        cat = os.path.basename(fp)[6:-4] or "extra"
        try:
            words = [w.strip() for w in open(fp, encoding="utf-8")
                     if w.strip() and not w.startswith("#")]
            if words:
                _EXTRA_CACHE[cat] = (0.85, words)
        except Exception:
            pass
    return _EXTRA_CACHE


# ============================================================
# 检测主入口
# ============================================================
class KeywordBaseline:
    name = "keyword-baseline"
    labels = ["SAFE", "UNSAFE"]
    version = "v2-industrial"

    def detect(self, text):
        raw = text or ""
        t = normalize(raw)
        t, homo_hits = apply_homophones(t)
        hits, score = list(homo_hits), 0.0

        # 词库（内置 + 外挂）
        for cat, (weight, words) in {**CATEGORY_WORDS, **_load_extra()}.items():
            for w in words:
                if w in t:
                    # 词长特异性加成：长词更具体，最高 +0.1
                    s = min(0.98, weight + min(0.1, len(w) / 40))
                    score = max(score, s)
                    hits.append(f"{cat}:{w}")

        # 正则规则
        for n, rx, w in _COMPILED:
            if rx.search(raw) or rx.search(t):
                score = max(score, w)
                hits.append(n)

        return {
            "label": "UNSAFE" if score >= 0.5 else "SAFE",
            "score": round(score, 3),
            "confidence": round(score, 3),
            "hits": hits[:12],
            "normalized_preview": t[:60],
            "threshold": 0.5,
        }

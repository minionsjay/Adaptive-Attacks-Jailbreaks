# AMS-RedTeam — 自适应红队评估框架

> 论文实现：**《The Attacker Moves Second: Stronger Adaptive Attacks Bypass Defenses
> Against LLM Jailbreaks and Prompt Injections》** (USENIX Security 2026)
>
> 用一个"**提出—打分—选择—更新**"的自进化攻击框架（MAP-Elites 岛模型进化搜索），
> 对 **2B / <1B 的越狱与提示注入检测模型**做强自适应评估：
> 静态测试集测的是"攻击者的弱"，只有让攻击者拿到反馈进化，才能测出"防御的强"。

| | |
|---|---|
| **自进化攻击底座** | Qwen3.8-27B-Uncensored-HauhauCS-Aggressive (GGUF)<br>→ 2×V100 (16GB×2) llama.cpp 双卡部署，见 [`remote/DEPLOY.md`](remote/DEPLOY.md) |
| **被测对象** | 2B / <1B 检测器：Meta PromptGuard 86M/22M/2B、ProtectAI DeBERTa 184M、规则基线 |
| **评估场景** | ① 越狱（victim LLM + judge 六档判定）② 提示注入（AgentDojo-lite：6 个 agent 工具链场景 + 目标动作判定） |
| **离线验证** | 无 GPU 也能跑全链路：`bash scripts/run_smoke.sh`（mock 攻击者 + 真实检测器） |

---

## 0. 不知道从哪开始？按你的情况选：

| 你的情况 | 看哪份 |
|---|---|
| **两台机器网络不通（git 传输）+ llama.cpp 已在跑 Qwen3.8，只想对比小检测器** | ★ [`remote/MY-SETUP.md`](remote/MY-SETUP.md)（4 步接入 + 一条命令出排行榜） |
| 从零开始：模型还没下载、环境还没装 | [`remote/QUICKSTART.md`](remote/QUICKSTART.md)（手把手：每步命令 + "看到什么算成功"） |
| git 中转传输的具体命令 | [`remote/GIT.md`](remote/GIT.md) |

本 README 其余部分是架构与设计说明，跑通后回头查阅即可。

## 1. 快速开始

```bash
pip install -r requirements.txt

# ① 离线冒烟（零下载：mock LLM + 规则基线，约 1 分钟）
bash scripts/run_smoke.sh

# ② 真实检测器冒烟（额外拉起 ProtectAI DeBERTa 184M，首次下载约 184MB）
bash scripts/run_smoke.sh --real

# ③ 单元测试（无需网络）
python tests/test_pipeline.py
```

单机部署到 2×V100（正式评估，整个项目都在那台机器上跑；**详细步骤看 [remote/QUICKSTART.md](remote/QUICKSTART.md)**）：

```bash
# 开发电脑（仅此一步）: 传代码
rsync -av --exclude redteam_output* ./redteam/ user@v100:~/ams-redteam/

# V100 机器上:
cd ~/ams-redteam/remote
bash setup_env.sh && QUANT=Q5_K_P bash download_model.sh   # 环境+模型（10-20分钟）
EVAL=1 bash start_all.sh        # tmux 一键: attacker+victim+detectors(+自动评估)
bash run_eval.sh --dry-run      # 或手动: 连通性检查 → run_eval.sh --mode full
```

## 2. 论文 → 工程的映射

| 论文组件 | 本项目实现 | 代码 |
|---|---|---|
| Propose（变异器 Gemini 2.5 Pro） | Qwen3.8-27B-Uncensored 批量产出 JSON（`improvement` + `triggers`），系统提示固定可缓存 | `ams/harness.py::propose` |
| Score（Scorer + critic） | 检测器打分 → victim/agent 真实反馈 → judge/goal 判定 → critic 1-10（贪心低温） | `ams/harness.py::score`、`ams/critic.py` |
| Select（MAP-Elites 岛模型） | 5 岛轮转 × (长度 10 bin × 多样性 10 bin) 网格，每格留最优 | `ams/controller.py` |
| Update（灵感组合） | 当前最佳 + 3 随机 elite + 5 邻近 bin + 5 随机池 | `ams/controller.py::inspiration_set` |
| 知防御而攻（注入防御论文摘要） | 检测器注册表自带 `methodology` 中文卡片喂给攻击者 | `detectors/registry.py` |
| 检测器反馈消融 | `evolution.feedback_level: none / flag / score` | `config.yaml` |
| AgentDojo 注入战场 | 6 个 AgentDojo-lite 场景（邮件/日历/差旅/文件/Slack/PR），目标动作判据 | `ams/scenarios/injection.py` |
| 成功判据 ground-truth | judge 六档（Y/YP/YD/NI/NR/NC）+ goal 工具调用匹配，与 critic 严格分离 | `ams/scenarios/` |
| 攻击成本透明披露 | queries-to-success / 代币 / 美元，进报告 | `ams/analysis/metrics.py` |
| 攻击即数据回流 | 绕过样本自动导出训练集（漏报正例+已抓+良性） | `ams/analysis/store.py::export_training_data` |

**扩展：09-SmallLM-Jailbreak（CCS 2026，浙大）论文复现**——该论文系统性评测了 59 个 SLM（135M–5B）
的越狱脆弱性与 5 种轻量防御，本框架把它的两块资产直接接入：

| 09 论文资产 | 本项目实现 | 用法 |
|---|---|---|
| 59 个 SLM 当 victim（Group I 稳健组 / Group II 脆弱组，含论文 ASR 数字） | `ams/victim_registry.py` 注册 15 个代表 + `remote/serve_victim_hf.py`（HF 官方权重 + chat template + 贪心解码，与论文评测方式一致） | `python remote/serve_victim_hf.py --id qwen2.5-1.5b --port 8001` |
| PPL Window 防御（窗口10/阈值6.031） | `ppl-window` 检测器：滑窗困惑度 + **自校准阈值**（小型 LM 对自然文本 PPL 在 20~100 量级，论文固定 6.031 不可移植；默认 Qwen2.5-1.5B 多语底座，可传固定阈值复现论文参数） | `remote/serve_detectors.sh` 含端口 8840 |
| Llama Guard 3-1B 防御 | `llama-guard-3-1b` 检测器（官方 S1-S13 提示格式，需 HF_TOKEN） | 端口 8841 |
| Self-Reminder / Retokenization（变换类防御） | **防御中间件**：不判分、改写进入 victim 的文本，可开关可叠加、与检测器组合 | `config.yaml::defense_middleware` |

复现实验设计（对照 09 论文结论）：① 同一攻击集打 Group I vs Group II victim → 验证脆弱性分组；
② 我们的自适应攻击 vs 论文 12 种固定攻击 → 看自适应增益；③ 开关 defense_middleware +
ppl-window/llama-guard → 复现 RQ3 防御结论（PPL 只防高困惑度后缀、Self-Reminder 仅对简单攻击有效等）。
实测参考（本仓库 `redteam_output_smoke2/`）：self_reminder 中间件开启后 direct 类攻击 ASR 降为 0
（论文结论"Self-Reminder 仅对简单攻击有效"）；ppl-window 自校准阈值 404（良性最大窗口 PPL 101×4），
GCG 式乱码 max_ppl≈6.6 万被拦，正常中英文本放行。

**语言维度扩展**（相对论文）：15 种语言/书写变体（繁中/拼音/缩写/粤语/谐音/emoji/混合语…）
作为 MAP-Elites 行为空间之外的 steering 维度——低资源语言是真实检测器的常见盲区。

## 3. 目录结构

```
redteam/
├── main.py                  CLI 入口（dry-run / jailbreak / injection / full / export / report）
├── config.yaml              主配置：四角色端点 + 进化参数 + 检测器列表 + 种子
├── requirements.txt
├── ams/                     核心包
│   ├── types.py             候选/场景/代际/检测器卡片 全量数据类型
│   ├── defenses.py          防御中间件：self_reminder / retokenization（09 论文）
│   ├── strategies.py        12 攻击策略 · 15 语言变体 · 11 注入手法原型
│   ├── controller.py        MAP-Elites 岛模型（5 岛 × 10×10 行为网格）
│   ├── critic.py            Critic 1-10 引导分（与 oracle 分离，防 reward hacking）
│   ├── victim_registry.py   09-SmallLM 论文 59 个 SLM 的 victim 注册表（Group I/II）
│   ├── harness.py           Propose→Score→Select→Update 主循环 + 双场景编排
│   ├── clients/
│   │   ├── llm.py           OpenAI 兼容客户端（重试/限速/成本/JSON 修复）
│   │   └── detector.py      统一检测器协议 + 反馈等级格式化
│   ├── scenarios/
│   │   ├── jailbreak.py     越狱：victim + judge 六档
│   │   └── injection.py     注入：AgentDojo-lite agent + 目标判据 + 6 内置场景
│   └── analysis/
│       ├── store.py         SQLite + JSONL + 训练数据回流
│       ├── metrics.py       ASR/绕过率/漏报率/混淆矩阵/queries-to-success
│       └── report.py        JSON+Markdown 报告 + 自动防御改进建议
├── detectors/               被测检测器侧
│   ├── registry.py          注册表（规模/标签/原理摘要/端口）
│   ├── serve_detector.py    统一 FastAPI 服务（classifier/generative/keyword 三后端）
│   └── keyword_baseline.py  规则基线
├── remote/                  2×V100 部署
│   ├── DEPLOY.md            部署文档（显存测算/Volta 注意事项/安全红线）
│   ├── setup_env.sh         llama.cpp CUDA 构建 + venv
│   ├── download_model.sh    GGUF 下载 + SHA256 校验
│   ├── serve_attacker.sh    27B 双卡 tensor-split（默认内嵌 MTP 加速）
│   ├── serve_victim.sh      victim 小模型（llama.cpp/GGUF 路径）
│   ├── serve_victim_hf.py   victim 小模型（HF 权重+官方chat template，09 论文方式）
│   ├── serve_detectors.sh   检测器批量拉起
│   ├── start_all.sh         tmux 一键启动（EVAL=1 连评估排队）
│   └── run_eval.sh          ★ 单机评估入口（激活 venv → python main.py）
├── scripts/
│   ├── mock_llm.py          离线 mock（mutator/victim/judge/critic/agent 五角色）
│   └── run_smoke.sh         本地冒烟（可选真实 DeBERTa）
├── tests/test_pipeline.py   单元测试（无需网络）
├── demo/index.html          ★ 项目演示页（结构/原理/流程/结果解读）
└── redteam_output*/         实验产物（db/jsonl/报告/训练数据）
```

## 4. 四个角色与运行时拓扑（单机模式）

**整个项目跑在一台 2×V100 机器上**（服务 + judge + 评估 runner 全部 localhost），
开发电脑只负责 rsync 代码、ssh 操作、scp 取报告，运行期零参与：

```
┌──────────────────── V100 机器（一台机器就是全部）────────────────────┐
│ GPU0+GPU1: llama-server:8000  Qwen3.8-27B-Uncensored (Q5_K_P)        │
│   ├─ mutator 提出攻击候选   ├─ critic 1-10 引导打分                   │
│   └─ judge 六档判定         （--parallel 4 共用一份权重）             │
│ CPU: llama-server:8001 victim 对齐小模型                             │
│ CPU: detector:8820/8810/8830/8840  DeBERTa/PromptGuard/规则/PPL      │
│ runner: bash remote/run_eval.sh → python main.py（全指向 127.0.0.1） │
│ 产物: redteam_output/（db / 报告 / 训练数据）                         │
└──────────────────────────────────────────────────────────────────────┘
开发电脑: rsync 代码 → ssh 操作 → scp 取报告（运行期零参与）
```

## 5. 输出与指标解读

- `report_<exp>.md / .json`：静态 ASR vs 自适应 ASR、绕过率、**漏报率（核心）**、
  误报率、混淆矩阵、分语言/策略/场景统计、queries-to-success、自动防御建议
- `redteam.db / candidates.jsonl`：每条候选全生命周期（含检测分数、victim 回复、
  agent 轨迹、judge 判定、critic 建议与成本）
- `exports/training_data_*.jsonl`：绕过样本（检测器漏报正例）+ 已拦截样本 + 良性负例，
  直接用于检测器的对抗训练回流

**怎么读结果**（论文口径）：静态 ASR 低 ≠ 防御强；要看自适应 ASR / 绕过率 / 漏报率，
以及首次成功花了多少次查询。评估只能"未能证伪防御"，不能证明防御稳健。

## 6. 冒烟实测（本项目仓库自带数据）

用 mock 攻击者 + **真实 ProtectAI DeBERTa v2 (184M)** 的完整运行
（`redteam_output_smoke/report_exp_20260830_173326_d189da.md`）：

- 注入场景 4/6 被攻破，成功 trigger 全是"**政策话术/前置流程伪装**"——
  与论文对检测器类防御的结论一致（脱离上下文无恶意特征）
- 越狱盲区集中在拼音/混合语（pinyin-abbr 80%、zh-en-mix 60% 绕过）
- queries-to-success：种子直接成功 ~6 次查询；进化找到的 15~30 次

## 7. 伦理与使用边界

- 仅用于**自有系统**的防御评估与对抗训练数据生产
- uncensored 底座只跑在隔离的研究机上，`serve_attacker.sh` 绝不暴露公网
- 产物含真实攻击样本，按敏感数据管理；引用请注明原论文

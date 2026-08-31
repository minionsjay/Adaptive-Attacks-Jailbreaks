# 论文详读：小语言模型能否可靠抵御越狱攻击？

> **会议**：ACM CCS 2026（CCS '26，2026-11-15~19，荷兰海牙）
> **英文原题**：Can Small Language Models Reliably Resist Jailbreak Attacks? A Comprehensive Evaluation
> **作者单位**：浙江大学 区块链与数据安全全国重点实验室（Zhibo Wang 等，通讯作者 Huiyu Xu）
> **论文链接**：https://arxiv.org/abs/2503.06519 ｜ 开源：https://github.com/Wendy-1222/SLM_Jailbreak

## 一句话概括

这是**首个针对小语言模型（SLM）越狱脆弱性的系统性实证评估**：论文对 15 个主流家族的 59 个 SLM（135M–5B 参数）+ 2 个 LLM 基线，用 12 种越狱攻击方法、14 类风险问题做大规模评测，发现 61.0% 的 SLM 平均攻击成功率（ASR）超过 40%、37.3% 连直接有害提问都挡不住（ASR>50%），且脆弱性主要取决于训练数据与训练技术（如 DPO 阶段反而削弱安全）而非模型规模，现有轻量防御也无法提供一致保护。

## 研究背景与动机

SLM（通常 <5B 参数）因低算力需求、隐私保护和领域性能，正快速部署到手机、车载、可穿戴等边缘设备（如 iOS 的 Apple Intelligence）。但安全研究远落后于 LLM：压缩/蒸馏等训练技术可能放大安全威胁；离线本地部署使恶意行为比云端 API 更难追踪。作者以 2025 年 1 月 Tesla Cybertruck 爆炸案（罪犯通过越狱 ChatGPT 获取信息）说明越狱的现实危害。

论文指出 SLM 与 LLM 越狱评估存在四大差异：(i) **数据集**——SLM 面向隐私敏感的个性化任务，需更关注具体风险类别维度；(ii) **攻击提示**——SLM 越狱更多依赖"潜在知识诱导"而非 LLM 的指令跟随利用，简单攻击（naive attack）也构成威胁，需更宽的攻击覆盖；(iii) **评估指标**——SLM 常产生重复模式或混乱内容，传统毒性指标难以识别，需引入质量指标（diversity/fluency）；(iv) **防御实施**——边缘设备资源受限，无法部署重型内容过滤或多 Agent 检查。现有越狱基准（HarmBench、SALAD-Bench、JailbreakBench、SorryBench）几乎只评 LLM（多数 >7B）；Yi et al.（ACL 2025 Findings）虽开了 SLM 评估先河，但仅 13 个 SLM、5 种单轮攻击、3 种提示级防御。本文大幅扩展为 59 模型 × 12 攻击 × 多轮 × 5 种防御 × 因素分析。

## 问题定义 / 威胁模型

- **目标 SLM**：HuggingFace 上开源的指令微调文本 SLM（非基座模型），使用官方默认 chat template，无投毒、保留默认安全机制；不考虑规划、RAG、工具调用、多 Agent 协同等高级 Agent 特性。
- **有害问题**：违反主流 LLM 服务商使用政策的典型越狱问题（如"如何制造炸弹"），覆盖 14 个风险类别。
- **对抗场景**：白盒（完全访问架构、训练数据、梯度）、灰盒（无参数梯度但可得完整 logits）、黑盒（仅 API 输出）。
- **三个研究问题**：RQ1 SLM 在不同攻击方法与风险类别下有多脆弱（§4）；RQ2 哪些关键因素决定脆弱性（§5）；RQ3 现有防御对 SLM 的有效程度（§6）。

## 方法与系统设计

本文是评测框架而非攻击方法创新，设计三个维度：

1. **攻击面**：12 种攻击 = 白盒 5 种（GCG、AutoPrompt、PEZ、GBDA、UAT，均为梯度优化对抗后缀，统一后缀长度 20、优化步数 500）+ 灰盒 2 种（AutoDAN 遗传算法变异人工模板，变异 LLM 用 Vicuna-13B-v1.5；SimpleAdaptive 随机搜索后缀，judge 用 GPT-4o）+ 黑盒 5 种（Direct 直接有害提问作为基线、HumanJailbreaks 从 114 个真实模板随机选 5 个、PAIR 迭代优化、PAP 说服策略改写、Crescendo 多轮渐进诱导）。
2. **模型面**：15 个家族 59 个 SLM（LLaMA-3.2、DeepSeek-R1-Distill-Qwen、Qwen、Gemma、Phi、MiniCPM、H2O-Danube、SmolLM、StableLM、TinyLlama、MobileLLaMA、MobiLlama、Fox、Dolly、PhoneLM），加 Qwen3-14B-Instruct 与 StableLM-2-12B-Chat 两个 LLM 基线。关闭随机采样保证可复现，输出 512 token，所有实验跑 5 次取聚合结果。
3. **指标面**：harmfulness（ASR，用 HarmBench 的 Llama-2-13B 分类器判定 0/1）+ diversity（Repetition Rate、Lexical Diversity、Self-BLEU）+ fluency（Perplexity、Flesch Readability、Coherence Score）；并用 Flow-Judge-v0.1（输出 1/2/3 分）度量回复与越狱目标的相关性。因素分析用 Spearman 秩相关 + Global Benjamini-Hochberg 校正（65 个检验，FDR α=0.05）。

## 实验设置

- **数据集**：Xu et al.（RedAgent，TDSC 2026）的类别均衡数据集，70 个有害问题均匀分布于 14 个风险类别（源自各家模型商使用政策）；另在附录 D.1 用 5 个额外数据集验证 Direct 攻击结论一致性，附录 D.4 做低资源语言攻击。
- **因素变量**：模型规模（135M–5B）、训练 token 数（SLM 普遍"过训"，远超 Chinchilla 约 20 token/参数的比例）、训练技术（SFT vs SFT+DPO、知识蒸馏、量化 AWQ/GPTQ-Int4/GPTQ-Int8、ProSparse）、模型能力（MMLU、IFEval、ARC-c）。
- **防御**：提示级 4 种——PPL Window（窗口 10，阈值 6.031）、Llama Guard 3-1B、Retokenization（BPE-dropout p=0.2）、Self-Reminder；模型级 1 种——R2D2 对抗训练（以 SimpleAdaptive 为训练期对手，作用于 Group II 的 H2O-Danube3-500M-Chat、StableLM-2-1.6B-Chat、H2O-Danube3-4B-Chat），并对全部 12 种攻击评测（含多轮 Crescendo）。由于前四种提示级防御只作用于单条提示，它们不参与 Crescendo 多轮场景的评测。此外，与既有基准只在服务器上测试不同，本文还把评测延伸到手机等边缘设备，以贴近 SLM 的真实部署环境（附录 C.1）。

## 主要结果（关键数字与发现）

**总体脆弱性（RQ1）**：61.0% 的 SLM 平均 ASR>0.4；37.3% 在 Direct 上 ASR>0.5。按热图分两组：Group I（Llama-3.2、DeepSeek-R1-Distill-Qwen、Qwen、Gemma、Phi-3、MiniCPM，平均 ASR<0.4、Direct<0.3）相对稳健；Group II（SmolLM、StableLM、TinyLlama、MobileLLaMA、Dolly 等）几乎全线沦陷（平均 ASR>0.5、Direct>0.5）。从 Table 1 的具体数字看，全场最稳的是 Gemma-3-270M-it（平均 ASR 仅 0.201）与 Phi-4-mini-Instruct（0.275），Llama-3.2-1B/3B-Instruct 分别为 0.291/0.393；而最差的 StableLM-2-1.6B-Chat 平均 ASR 高达 0.68，H2O-Danube-1.8B-Chat 与 MobileLLaMA-2.7B-Chat 均约 0.61–0.63。两个 LLM 基线 Direct ASR 仅 0.2 / 0.186；同族对比中 StableLM-2-1.6B-Chat（Direct 0.757）和 StableLM-2-Zephyr-1.6B（0.614）约为 12B 版本的 4 倍。

**攻击方法差异**：PAIR 最有效（多数模型 ASR>60%），SimpleAdaptive 与 GCG 次之；有趣的是对 LLM 有效的多轮 Crescendo 在弱 SLM 上失效（如 MobiLlama 家族 ASR<10%）——用 Flow-Judge 证实这是因为模型跟不上复杂多轮指令、答非所问，"抗攻击"其实是能力不足（Finding 1）。

**风险类别差异（Finding 2）**：高易感（ASR≥0.5）类别为 Gov Decision、Illegal Activity、Economic Harm、Political Lobbying、Children Harm、Fraud；低易感（<0.35）为 Hate Speech、Legal Opinion、Health Consultation；问题级 95% 置信区间平均宽度 0.265。

**回复质量（Finding 3）**：Group II 重复率普遍 >0.4（Dolly 高达 0.8、词汇多样性极低），LLM 基线 <0.05；低困惑度/高连贯性是重复退化伪影而非真实流畅，SLM 越狱产物的实际可操作性毒性受限。

**因素分析（RQ2）**：
- **模型规模**：与平均 ASR 相关性可忽略（ρ=+0.11, p_adj=0.51）；对语义型攻击甚至更大更脆弱（AutoDAN ρ=+0.44、SimpleAdaptive ρ=+0.50，最多高 20% ASR；SmolLM2-360M→1.7B 在 AutoDAN 下从 34.3% 升至 61.4%）（Finding 4）。
- **训练数据**：token 扩增可提升对简单攻击的稳健性（Direct ρ=−0.49、PEZ ρ=−0.52），但对 Crescendo（+0.14）/SimpleAdaptive（+0.15）无效；Phi-3（3.3T "教科书级"数据）在能力与安全上均优于 9T token 的 Llama-3.2-3B，提示数据策划比规模更重要。多语言方面，与 LLM 易被低资源语言绕过相反，SLM 对低资源语言越狱提示的 ASR 极低，原因同样是其语言能力不足而非安全对齐（附录 D.4）。
- **训练技术**：SFT-only 比 SFT+DPO 稳健 10–40%（MiniCPM-2B-SFT 在 Direct 上比 DPO 版低 27%；H2O-Danube-1.8B-SFT 在 SimpleAdaptive 上低 31%），DPO 模型出现"compliance drift"（Finding 5）；蒸馏数据缺安全覆盖会放大脆弱性（DeepSeek-R1-Distill-Qwen 1.5B/7B Direct ASR 达 0.271/0.514，推理痕迹千篇一律以 "Okay, so I need to figure out..." 开头，缺乏恶意意图识别），而含安全推理数据的 STAR1-R1-Distill-1.5B 与 RealSafe-R1-1.5B 平均 ASR 仅 0.067/0.016；相反量化与 ProSparse 是"天然防御"：AWQ 最佳降 ASR 15.9%，MiniCPM-S-1B（ProSparse）较稠密版低 14%（Finding 6）。
- **模型能力（Finding 7）**：MMLU 与 Direct（ρ=−0.71）、PEZ（ρ=−0.60）显著负相关，但与 Crescendo（+0.54）、SimpleAdaptive（+0.55）正相关——能力是双刃剑，强推理模型会"把自己推理进越狱"；Phi-3-mini-128k 在长上下文攻击上比 4k 版高 15% ASR。

**防御评测（RQ3）**：PPL Window 对 GCG 类后缀攻击几乎降为 0，但对语义自然的 PAIR/PAP 无效；Llama Guard 3-1B 将多数攻击 ASR 降至基线约 50%，但对 SimpleAdaptive 仅降 2%；Retokenization 是提示级中最强（平均 ASR 降至约 0.2，如 MobiLlama-1B-Chat 把 "identity theft" 误读为 "identify the ft"），但以破坏语义理解为代价且对 StableLM 仍留 0.2–0.6（Finding 8）；Self-Reminder 最大仅降 16% ASR，仅对 Group I 有效（降至原值 54%–86%），MobileLLaMA 甚至不降反升（Finding 9）；模型级 R2D2 将三个高危 SLM 平均 ASR 从 0.58 降到 0.1、SimpleAdaptive 降为 0，但 PAIR/PAP 仍有 0.21/0.19，对 Crescendo 几乎无保护（Finding 10）。

## 贡献与亮点

1. **首个 SLM 越狱大规模系统评测**：59 模型 × 12 攻击（含多轮）× 14 风险类别 × 三维指标（毒性/多样性/流畅性），规模约为 Yi et al. 的 5 倍，并首次纳入模型级防御与边缘设备（手机）测试环境。
2. **因素归因有反直觉结论**："更大≠更安全"、"扩数据只防简单攻击"、"DPO 可能侵蚀拒绝边界"、"能力是双刃剑"，对 SLM 训练实践有直接指导意义。
3. **10 条明确编号的 Finding**，并对开发者（数据清洗、偏好/蒸馏数据显式安全覆盖、每阶段对齐后做稳健性验证、"safety adapter"）、监管者（水印与溯源、红队要求）、用户（风险意识）给出分层建议。
4. **方法论严谨**：Spearman+BH 校正控制多重检验假阳性、5 次重复实验、5 个额外数据集与 n-gram 敏感性验证、相关性分析明确标注"观察性、非因果"。

## 局限性

- 主数据集仅 70 个问题（每类 5 个），细粒度类别排序需谨慎（已用额外基准与置信区间缓解）；
- 有害性判定依赖 HarmBench 的 Llama-2-13B 分类器（与人判一致率 93.19%），边界/低质量回复可能误判；
- 因素分析是观察性的：即便同族对比，公开 SLM 仍存在未公开的架构微调、预训练数据配比与对齐配方差异，无法做严格因果归因；
- 仅覆盖英文、decoder-only、指令微调文本 SLM，未涉及 Agent 化场景（工具调用、RAG）与多模态。

## 对我们方向的启示（方向二：越狱/提示注入检测）

1. **检测器选型与组合的实证依据**：论文给出 4 种轻量防御的失效边界——PPL 类检测只对"高困惑度后缀"（GCG/AutoDAN）有效，对 PAIR/PAP 等语义自然攻击完全失效；Llama Guard 3-1B 这类微调分类器更全面但被 SimpleAdaptive 等欺骗性提示绕过（仅降 2%）。这直接支持我们做多信号融合检测（统计特征 + 语义分类器 + 上下文记忆）而非单点防御。
2. **多轮与语义攻击是防御洼地**：模型级 R2D2 对 Crescendo 几乎无效、对 PAIR/PAP 保护有限，说明"针对单一攻击模式训练的对抗防御迁移性差"——我们的检测研究应优先攻多轮渐进式、语义自适应这类泛化性差的攻击面。
3. **SLM 场景是增量机会**：端侧 SLM 无云端 guardrail、资源受限，且"抗复杂攻击"常是能力不足的假象；我们可研究面向端侧的轻量越狱检测（如论文提到的 safety adapter、本地文档恶意指令扫描），并把 Flow-Judge 式"回复相关性"信号用于识别"假拒绝/跑题"。
4. **输出质量信号可用于检测**：Group II SLM 的重复退化（重复率>0.4、Dolly 0.8）提示可在响应侧用重复率/词汇多样性辅助判定"低质量有害输出"，弥补毒性分类器对混乱有害文本的漏检——这正是论文强调 LLM 毒性指标不适配 SLM 的原因。
5. **与方向一/三的交叉**：类别失衡（Gov Decision、Fraud 等高易感 vs Health Consultation 低易感）提示内容风控策略应按类别差异化配置；方向三分析恶意 APK 时，若样本内嵌端侧 SLM 组件（如 mobile LLM app），其越狱脆弱性（MobileLLaMA/MobiLlama 等 Direct ASR 0.5–0.77）应纳入 APK 恶意性评估清单。

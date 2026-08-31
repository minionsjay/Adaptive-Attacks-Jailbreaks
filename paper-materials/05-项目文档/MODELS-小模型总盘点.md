# 两篇论文用过的小模型总盘点（MODELS.md）

> 按"在框架里扮演的角色"整理 06-Attacker-Moves-Second（USENIX Sec 2026）与
> 09-SmallLM-Jailbreak（CCS 2026）用到的全部模型；标注本项目是否已支持、怎么接入。

## A. Victim（被攻击对象）——09 论文 59 个 SLM 的代表阵容

★ = 已在 `ams/victim_registry.py` 注册，`serve_victim_hf.py --id xxx` 直接用；
`bash remote/download_small_models.sh /data/models victims-all --write-env` 一键全下。

### Group I（论文：相对稳健，平均 ASR<0.4）

| victim | 规模 | 论文平均 ASR | 门控 | 备注 |
|---|---|---|---|---|
| ★ realsafe-r1-1.5b | 1.5B | **0.016** | 开放 | 全场最稳 R1 系——安全蒸馏天花板 |
| ★ star1-r1-distill-1.5b | 1.5B | 0.067 | 开放 | 含安全推理数据的蒸馏（Finding 6 正面证据） |
| ★ gemma-3-270m | 270M | **0.201** | HF_TOKEN | 全场最稳 SLM |
| ★ phi-4-mini | 3.8B | 0.275 | 开放 | 3.3T 精选数据（"数据策划>规模"） |
| ★ llama-3.2-1b / 3b | 1B/3B | 0.291 / 0.393 | HF_TOKEN | 端侧主力 |
| ★ minicpm-2b-sft | 2B | 0.30 | 开放 | SFT-only 比 DPO 版稳 10-40%（Finding 5） |
| ★ qwen2.5-0.5b / 1.5b | 0.5B/1.5B | ~0.35 | 开放 | **推荐默认**（中文好、免登录） |
| ★ qwen3-1.7b | 1.7B | — | 开放 | 代际验证用 |

### Group II（论文：几乎全线沦陷，平均 ASR>0.5）

| victim | 规模 | 论文平均 ASR | 门控 | 备注 |
|---|---|---|---|---|
| ★ stablelm-2-1.6b | 1.6B | **0.68（全场最差）** | HF_TOKEN | Direct 0.757 ≈ 12B 版 4 倍 |
| ★ stablelm-2-zephyr-1.6b | 1.6B | 0.55 | 许可 | 同上，同族对照 |
| ★ h2o-danube-1.8b | 1.8B | 0.62 | 开放 | 沦陷组代表 |
| ★ mobillama-2.7b | 2.7B | 0.62 | 开放 | Crescendo 下 ASR<10% 是能力不足假象 |
| ★ dolly-v2-3b | 3B | 0.60 | HF_TOKEN | 重复率 0.8——低质量有害输出代表（Finding 3） |
| ★ r1-distill-qwen-1.5b | 1.5B | 0.55 | 开放 | **无安全数据的蒸馏**（与 STAR1/RealSafe 三连对照） |
| ★ smollm2-360m | 360M | 0.52 | 开放 | 360M→1.7B 在 AutoDAN 下反而 34%→61%（Finding 4） |
| ★ tinyllama-1.1b | 1.1B | 0.57 | 开放 | 经典端侧 |
| ★ mobillama-1b | 1B | 0.58 | 开放 | 移动端专用 |
| ★ h2o-danube3-500m | 500M | 0.55 | 开放 | R2D2 对抗训练的对象 |
| ★ fox-1-1.6b | 1.6B | 0.55 | 开放 | 边缘部署家族 |
| ★ phonelm-0.5b | 0.5B | 0.52 | 开放 | 手机端（09 论文 15 家族之一） |

### LLM 基线（对照）
| ★ qwen3-14b | 14B | Direct 0.2 量级 | 开放 | 论文两个 LLM 基线之一（另一个 StableLM-2-12B-Chat） |

> 09 论文还有个别家族（MobileLLaMA 其他尺寸、MobiLlama 其他尺寸）未逐一注册，
> 需要时用 `--hf <任意HF id>` 直接跑。

**推荐实验组合**：`realsafe-r1-1.5b + star1-r1-distill-1.5b + r1-distill-qwen-1.5b`
三连——同为 1.5B 推理蒸馏，安全数据有无带来 0.016 / 0.067 / 0.55 的天壤之别，
是 09 论文 Finding 6 最漂亮的对照，我们的自适应攻击可以直接复验。

## B. 检测器 / 防御

### 已支持（`detectors/registry.py`，统一 /v1/detect）

| 注册 id | 来源论文 | 规模 | 门控 |
|---|---|---|---|
| ★ deberta-injection-v2 / v1 | 06（Protect AI 防御） | 184M | 开放 |
| ★ prompt-guard-86m | 06（PromptGuard 防御，v1） | 86M | HF_TOKEN（实测） |
| ★ prompt-guard-2-86m / 22m | Meta 官方 | 86M/22M | HF_TOKEN（实测） |
| ★ prompt-guard-2-2b | 06（PromptGuard 2B 版） | **2B** | HF_TOKEN |
| ★ llama-guard-3-1b | 09（RQ3 防御） | 1B | HF_TOKEN |
| ★ ppl-window | 09（RQ3 防御：PPL 窗口10/阈值自校准） | 1.5B底座 | 开放 |
| ★ keyword-baseline | 基线 | 规则 | 零下载 |
| ★ self_reminder / retokenization | 09（变换类防御） | — | 防御中间件 |

### 06 论文用过但暂未支持（按需扩展）

| 防御 | 类别 | 状态 |
|---|---|---|
| PIGuard | 检测器 | 研究代码开源、权重未完全开放；接入=实现 /v1/detect 三字段 |
| Model Armor | 检测器 | Google 闭源，无法本地复现 |
| Spotlighting / Prompt Sandwiching | 提示类防御 | 纯 prompt 工程——可在我们 harness 的 defense_middleware 里加两个模板即复现 |
| RPO | 提示类防御（系统提示后缀） | 同上，模板级 |
| Circuit Breakers / StruQ / MetaSecAlign | 对抗训练类 | 有开源模型（MetaSecAlign-70B 在 HF）；属"模型级"victim 变体而非检测器 |
| Data Sentinel | 蜜罐密钥 | 需要部署其密钥体系，工程量大 |
| MELON | 双跑检测 | 需双份推理对比，可做成中间件 |
| R2D2（09 论文，模型级） | 对抗训练 | checkpoint 在 github.com/Wendy-1222/SLM_Jailbreak |

## C. Judge / 裁判类（自动判定攻击是否成功）

| 模型 | 论文用法 | 本项目状态 |
|---|---|---|
| HarmBench Llama-2-13B 分类器 | 06 的 ASR 判定（0/1） | 可选接入：作 judge 的二值兜底（我们的 judge 是六档 LLM，更细但需强模型） |
| Flow-Judge-v0.1 | 09 的回复相关性（1/2/3 分） | 未接入；适合识别 SLM"答非所问式假抗攻击" |
| GPT-4o | 09 的 SimpleAdaptive judge | 外部 API，config.yaml judge 段可指 |
| （06 原文）Gemini 2.5 Pro | mutator+critic+judge 全包 | 外部 API；我们用 Qwen3.8-27B-Uncensored 本地替代 |

## D. Mutator / Critic（攻击侧）

| 模型 | 论文用法 | 本项目状态 |
|---|---|---|
| Gemini 2.5 Pro | 06 的 mutator（temp 1.0/top_p 0.95/top_k 64）+ critic（贪心） | 外部 API 路线 |
| **Qwen3 235B / Qwen3 32B** | 06 表 7：开源替代 mutator/critic，ASR 100% / 91%，省 10 倍费 | ★ 依据——我们选 **Qwen3.8-27B-Uncensored** 本地部署等价复现 |
| Vicuna-13B-v1.5 | 09 的 AutoDAN 遗传变异器 | 未接入（我们用进化搜索而非遗传算法） |
| 攻击者底座（"只训 helpfulness 无对齐"的闭源模型） | 06 的 RL 攻击者 | ★ Qwen3.8-27B-Uncensored（0/465 拒答）即其开源对应物 |

## 一键下载速查

```bash
bash remote/download_small_models.sh /data/models                    # 免登录全家桶(检测器+victim三件套)
bash remote/download_small_models.sh /data/models victims-all        # 16个免登录 victim(~35GB)
bash remote/download_small_models.sh /data/models victims            # 推荐三件套
bash remote/download_small_models.sh /data/models victim:realsafe-r1-1.5b victim:star1-r1-distill-1.5b victim:r1-distill-qwen-1.5b  # Finding 6 三连对照
bash remote/download_small_models.sh /data/models --with-gated --write-env   # 含门控(先 huggingface-cli login)
```

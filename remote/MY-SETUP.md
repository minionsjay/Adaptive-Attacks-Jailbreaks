# 我的接入教程：llama.cpp 已跑好 + 只想对比小检测器

> 适用你的情况：
> ① 两台电脑网络不通 → 用 git 传项目（见 [`GIT.md`](GIT.md)）
> ② V100 机器环境已配好，**llama.cpp 已经跑着 Qwen3.8-27B**
> ③ 目标：**测试不同小模型（2B / <1B）的检测能力**，看谁强谁弱
>
> 全程只在 V100 机器操作，共 4 步，最后一条命令出排行榜。

---

## 第 1 步：确认你已有的 llama-server 地址和模型名（1 分钟）

```bash
# 常见端口：8080(llama-server默认) / 8000。两条都试一下：
curl -s http://127.0.0.1:8080/v1/models
curl -s http://127.0.0.1:8000/v1/models
```
记下两样东西：**端口** 和返回里的 **"id"**（模型名）。例：
```json
{"data":[{"id":"Qwen3.8-27B-Uncensored-...-Q5_K_P.gguf","object":"model"}]}
```

## 第 2 步：改配置指向它（1 分钟）

```bash
cd ~/ams-redteam
vi config.yaml          # 只改 3 处的 base_url 和 model（attacker / critic / judge）
```
```yaml
attacker:
  base_url: "http://127.0.0.1:8080/v1"     # ← 改成你的端口
  model: "Qwen3.8-27B-...-Q5_K_P.gguf"     # ← 改成 /v1/models 返回的 id
critic:
  base_url: "http://127.0.0.1:8080/v1"     # ← 同上
  model: "Qwen3.8-27B-...-Q5_K_P.gguf"
judge:
  base_url: "http://127.0.0.1:8080/v1"     # ← 同上
  model: "Qwen3.8-27B-...-Q5_K_P.gguf"
```
> 三个角色共用你这一个服务即可，不用起三个。

**顺手配模型路径**（victim/检测器以后要下载小模型，别挤系统盘）：
```bash
vi remote/models.env     # 取消注释改:
# HF_HOME="/data/hf_cache"
# MODEL_DIR="/data/models"
```

## 第 3 步：起 victim + 先测一个检测器（5 分钟）

**victim**（被攻击的对齐小模型，必须要有；另开一个 tmux 窗口）：
```bash
cd ~/ams-redteam
python remote/serve_victim_hf.py --id qwen2.5-1.5b --port 8001
# 成功标志: [victim-hf] ready :8001（首次自动下载 ~3GB 到 HF_HOME）
```

**连通性体检**（victim 起来后）：
```bash
cd ~/ams-redteam/remote
bash run_eval.sh --dry-run
# Mutator/Victim/Judge/Critic 和 Detector 们全 OK 就过关
# （Detector FAIL 正常——还没起，下一步脚本会自动拉起）
```

## 第 4 步：一条命令跑检测器对比（★ 核心）

```bash
cd ~/ams-redteam
bash remote/compare_detectors.sh
```

**它自动做的事**：对名单里每个检测器 → 拉起服务（首次自动下载模型）→ 单独跑一轮
进化攻击评估 → 关掉 → 换下一个 → 最后汇总成**排行榜**。

默认对比 3 个无门控检测器：`keyword-baseline`（规则）、`deberta-injection-v2`（184M）、
`prompt-guard-86m`（86M）。想加/换名单和规模：

```bash
# 加上 09 论文的 ppl-window（1.5B 底座）:
DETECTORS_TO_COMPARE="keyword-baseline deberta-injection-v2 prompt-guard-86m ppl-window" \
  bash remote/compare_detectors.sh

# 更大规模（更准但更久）;  full 模式连 6 个注入场景一起测:
GENERATIONS=8 POPULATION=8 bash remote/compare_detectors.sh
MODE=full bash remote/compare_detectors.sh
```

**门控模型**（需要 HF 许可）：huggingface.co 上接受 Llama 协议 → 机器上
`huggingface-cli login` → 名单里加 `llama-guard-3-1b`、`prompt-guard-2-2b` 即可。

## 看结果

```bash
cat redteam_output_compare/comparison.md     # ★ 最终排行榜
```

长这样（绕过率升序 = 从强到弱）：

| 排名 | 检测器 | 规模 | 绕过率↓ | 漏报率↓ | 误报率↓ | F1↑ | 首破queries | 最弱语言 |
|---|---|---|---|---|---|---|---|---|
| 1 | deberta-injection-v2 | 184M | 18.1% | 41.8% | 30.0% | 0.52 | 15 | pinyin-abbr |
| 2 | keyword-baseline | 规则 | 25.0% | 55.6% | 95.0% | 0.24 | 10 | zh-number |
| ... |

**怎么读**：绕过率/漏报率越低 = 检测能力越强；误报率 = 误伤正常流量的程度（要和漏报
一起看，只有两者都低才是真强）；首破 queries = 攻击者几个查询就找到绕过（越小越脆）；
最弱语言 = 该检测器该补训练数据的方向。每个检测器的完整细节看同目录下
`report_exp_*.md`（里面有分语言/分策略盲区、Top 绕过样本、自动改进建议）。

单个检测器深挖：
```bash
ls redteam_output_compare/report_*.md
cat redteam_output_compare/report_exp_xxxx.md
```

## 换不同 victim 再对比一轮（可选：09 论文玩法）

同一批攻击打不同 victim，能看"哪类小模型更容易被打穿"：
```bash
python remote/serve_victim_hf.py --id smollm2-360m --port 8001   # 换沦陷组 victim
bash remote/compare_detectors.sh                                  # 结果在另一个目录会混
# 建议换输出目录跑:
COMPARE_OUT=redteam_output_smollm bash remote/compare_detectors.sh
```
victim 名单：`qwen2.5-1.5b`（稳健组）/ `smollm2-360m`、`tinyllama-1.1b`（沦陷组）/
`r1-distill-qwen-1.5b`（推理蒸馏）等，见 `ams/victim_registry.py`。

## 常见问题（这个场景专属）

| 症状 | 解决 |
|---|---|
| dry-run Mutator FAIL | config.yaml 的 base_url/model 没改成你 llama-server 的（第 2 步） |
| llama-server 忙不过来/超时 | 正常，27B 吞吐有限；把 config.yaml 里 attacker 的 `timeout` 调大到 1200 |
| compare_detectors 中途卡在下载 | 首次要下检测器模型（184M~1.5B），等它；之后都走缓存 |
| 想停掉重来 | `tmux kill-session -t ams`；`lsof -i:8001` 找残留进程 |
| 检测器启动超时被跳过 | 单独手动起看报错: `cd detectors && python serve_detector.py --id xxx --port 8820` |

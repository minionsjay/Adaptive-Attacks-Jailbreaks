# 部署指南（单机模式）— 2×V100（Volta, 16GB×2）

> **部署形态**：整个项目（27B 攻击者 + victim + 检测器 + judge + 评估 runner）
> **全部跑在这一台 V100 机器上**，所有服务走 localhost。开发电脑只做一件事：
> 把代码 rsync 过去，之后 ssh 上去操作；结果文件按需 scp 取回。

## 0. 前置条件

| 项 | 要求 |
|---|---|
| GPU | 2× Tesla V100 16GB（Volta sm_70，llama.cpp CUDA 官方支持） |
| 驱动 | NVIDIA driver ≥ 530 |
| 内存 | 建议 ≥ 64GB（victim/ppl-window/检测器可全部跑 CPU，合计 ~12GB RAM） |
| 磁盘 | ≥ 60GB 空闲（27B GGUF 20GB + 检测器 + 缓冲） |
| 网络 | 首次需访问 huggingface.co（下载模型）；运行期完全离线可用（judge 也用本机 27B） |

## 1. 单机拓扑（谁在哪跑）

```
┌──────────────────── V100 机器（一台机器就是全部）────────────────────┐
│                                                                      │
│  GPU0 + GPU1（tensor-split 0.5,0.5）                                  │
│  └─ llama-server :8000   Qwen3.8-27B-Uncensored Q5_K_P (~10GB/卡)    │
│       ├─ mutator（攻击变异器）  ├─ critic（1-10 引导分）               │
│       └─ judge（六档判定）       ← --parallel 4 三角色并发共用一份权重  │
│                                                                      │
│  CPU（或富余显存）                                                    │
│  ├─ llama-server/serve_victim_hf :8001   victim 对齐小模型            │
│  └─ 检测器 FastAPI（统一 /v1/detect）                                  │
│       ├─ :8820 deberta-injection-v2 (184M)                            │
│       ├─ :8810 prompt-guard-86m        ├─ :8830 keyword-baseline      │
│       ├─ :8840 ppl-window (1.5B底座)   └─ :8841 llama-guard-3-1b(可选)│
│                                                                      │
│  runner（就是本机的一个进程）                                          │
│  └─ bash remote/run_eval.sh → python main.py   全部指向 127.0.0.1     │
│                                                                      │
│  产物: ~/ams-redteam/redteam_output/（db/报告/训练数据）               │
└──────────────────────────────────────────────────────────────────────┘
开发电脑: 只 rsync 代码、ssh 操作、scp 取报告 —— 运行期零参与
```

## 2. 部署步骤（在 V100 机器上）

```bash
# ① 开发电脑：传代码（仅此一步用到开发电脑）
rsync -av --exclude redteam_output* ./redteam/ user@v100:~/ams-redteam/

# ② V100 机器上：
cd ~/ams-redteam/remote
bash setup_env.sh                     # 构建 llama.cpp(CUDA) + venv 装全部依赖（10-20分钟）
QUANT=Q5_K_P bash download_model.sh   # 下载 27B GGUF 20.2GB（SHA256 校验）

# ③ 一键启动（tmux 会话 ams：attacker/victim/detectors 三窗口）
bash start_all.sh
#   或连评估一起排队：EVAL=1 bash start_all.sh

# ④ 跑评估（同机另一终端 / tmux eval 窗口）
bash run_eval.sh --dry-run                         # 连通性检查（应全 OK）
bash run_eval.sh --mode jailbreak --generations 3  # 小规模试跑
bash run_eval.sh --mode full                       # 正式全量
bash run_eval.sh --mode report --exp-id exp_xxx    # 重出报告 / export 导训练数据
```

```bash
# ⑤ 开发电脑取结果
ssh user@v100 'tail -50 ~/ams-redteam/redteam_output/report_*.md'
scp -r user@v100:~/ams-redteam/redteam_output ./   # 拉整个产物目录
```

## 3. 显存与量化选型（2×V100-16G）

| 量化 | 权重 | 每卡 | 建议上下文 | 说明 |
|---|---|---|---|---|
| **Q5_K_P（默认）** | 20.2GB | ~10.1GB | 16K | 质量优先，论文级复现推荐 |
| Q4_K_P | 17.9GB | ~9.0GB | 32K | 更大上下文（长注入文档），每卡余 ~6GB 可放 victim/检测器 |
| IQ4_XS | 15.7GB | ~7.9GB | 32K+ | 显存余量最大 |
| Q6_K_P | 25.9GB | ~13.0GB | ≤8K | 上下文太小，不推荐 |

KV cache 参考值（Qwen3.8-27B, 64 层）：16K ctx ≈ 3.2GB（两卡分摊）。
**Volta 注意**：不支持 bf16（GGUF 天然规避）；`--flash-attn` 在 Volta 不稳，脚本默认 `FA=0`；
mmproj 视觉投影器无需下载。加速：默认 `SPEC=embedded`（`--spec-type draft-mtp`，GGUF 内嵌
NextN 头，免补丁）；官方 FastMTP sidecar 需 `FASTMTP_PATCH=1` 重建，最高再 3×。

**内存预算（CPU 侧）**：victim Qwen2.5-1.5B fp32 ≈ 6GB + ppl-window 1.5B ≈ 3GB + 小检测器
<1GB + llama-server 系统开销 ≈ 12GB RAM。victim 也可用 `--device cuda:0` 放进 GPU 富余
（Q4_K_P 时每卡余 ~6GB，1.5B fp16 3.5GB 放得下）。

## 4. 检测器清单

| id | 规模 | 门控 | 端口 | 备注 |
|---|---|---|---|---|
| deberta-injection-v2 | 184M | 开放 | 8820 | ProtectAI，生产最常见 |
| prompt-guard-86m | 86M | **HF_TOKEN** | 8810 | Meta v1，唯一 3 分类（实测需接受许可） |
| prompt-guard-2-86m / 22m | 86M/22M | **HF_TOKEN** | 8811/8812 | Meta v2 二分类（实测需接受许可） |
| keyword-baseline | 规则 | 零下载 | 8830 | 冒烟/下限基线 |
| ppl-window | 1.5B底座 | 开放 | 8840 | 09 论文防御复现，自校准阈值 |
| **llama-guard-3-1b** | **1B** | **HF_TOKEN** | 8841 | HF 页面接受 Llama 许可 → `huggingface-cli login` |
| **prompt-guard-2-2b** | **2B** | **HF_TOKEN** | 8813 | 同上；建议 `DEVICE=cuda:1` |

2B 级检测器放 GPU 时注意与 27B 共卡：Q5_K_P 每卡余 ~4GB（2B fp16 ≈5GB 放不下），
建议改用 Q4_K_P 或让 2B 检测器跑 CPU（慢但可用）。

**SLM victim（09-SmallLM-Jailbreak 论文 59 模型阵容见 `ams/victim_registry.py`）**：
```bash
python remote/serve_victim_hf.py --id qwen2.5-1.5b --port 8001        # Group I，无门控
python remote/serve_victim_hf.py --id smollm2-360m --port 8001        # Group II 对照
python remote/serve_victim_hf.py --hf <任意HF模型id> --device cuda:0  # 自定义
# 官方权重 + 官方 chat template + 贪心解码 —— 与 09 论文评测方式一致
```

## 5. 吞吐预估

- V100 双卡 Q5_K_P：约 12–20 tok/s；`--spec-type draft-mtp` 内嵌加速后约 +60~120%
- 27B 三角色共用一份权重（llama-server `--parallel 4` 排队复用），无需三份显存
- 一次完整评估（3 检测器 × 越狱 15 代 + 6 注入场景）≈ 数小时量级；先 `--generations 3`
  小规模试跑确认链路，再全量
- 评估运行期**完全离线**（judge 默认本机 27B；如需换外部 API 见 config.yaml 注释）

## 6. 安全红线（必读）

- **uncensored 模型只用于研究**：单机模式下所有服务绑 127.0.0.1 或内网即可；
  `serve_attacker.sh` 默认绑 0.0.0.0 便于灵活使用，**上生产网络前请改为内网绑定 +
  防火墙白名单，绝不能暴露公网**
- 评估产物（redteam_output/）含真实攻击样本，按敏感数据管理；scp 传输走加密通道
- 目标遵守论文伦理声明：只测自己的系统，披露成本与负责任使用范围

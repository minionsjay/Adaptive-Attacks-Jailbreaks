# llama-server 启动参数详解（Qwen3.8-27B @ 2×V100）

> 针对你的机器（2×V100 16GB，Volta 架构）逐参数讲清楚：为什么这么设、
> 改了会怎样。**TL;DR 命令在第一节，直接抄**。

---

## 一、直接抄的命令（推荐：Q5_K_P + 内嵌 MTP 加速，不用额外文件）

```bash
llama-server \
  -m /你的路径/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-Q5_K_P.gguf \
  --alias "Qwen3.8-27B-Uncensored-Aggressive" \
  --host 0.0.0.0 --port 8000 \
  -ngl 999 \
  --tensor-split 0.5,0.5 \
  -c 32768 \
  --parallel 4 \
  --cont-batching \
  --flash-attn 0 \
  --spec-type draft-mtp \
  --jinja
```

如果报 `unknown argument: --spec-type`（llama.cpp 版本偏旧），把那一行删掉先用，
速度慢些但完全能跑；想提速就重新编译新版 llama.cpp。

## 二、每个参数为什么这么设

| 参数 | 值 | 为什么 |
|---|---|---|
| `-m` | 你的 gguf 路径 | 27B 主模型。见第三节量化选择 |
| `--alias` | `Qwen3.8-27B-Uncensored-Aggressive` | 对外的模型名。**必须和 config.yaml 里的 `model:` 一致**（或干脆用 `/v1/models` 返回的 id） |
| `--host/--port` | `0.0.0.0:8000` | 8000 是本项目 config 默认端口；单机跑其实 `127.0.0.1` 更安全 |
| `-ngl` | `999` | 全部 64 层上 GPU（数值只要 ≥ 层数即可） |
| `--tensor-split` | `0.5,0.5` | **两块卡均分权重**：Q5_K_P 20.2GB → 每卡 ~10.1GB，16GB 卡放得下还留 KV 空间 |
| `-c` | `32768` | **总上下文，会被 `--parallel` 平分！** 4 slot → 每 slot 8K。本项目 mutator 单次请求峰值 ~6-7K token（系统提示 2.5K + 灵感组合 1.5K + 输出 3K），8K/slot 刚好够。**设 16384 会导致长请求被截断** |
| `--parallel` | `4` | 4 个并发槽位：mutator + critic + judge 共用一个服务，偶尔并发 |
| `--cont-batching` | — | 连续批处理，多请求时不用排队等整批 |
| `--flash-attn` | `0` | **V100(Volta) 必须关**：llama.cpp 的 FA 内核对 Volta 支持不稳，会崩或出错结果。关掉用标准 attention，性能损失不大 |
| `--spec-type` | `draft-mtp` | **内嵌 MTP/NextN 加速**：GGUF 里本来就带 MTP 头（HauhauCS 保留了 Qwen3.8 原生 NextN），加这个 flag 启用推测解码，**通常 +60~120% 生成速度，零额外文件**。模型 README 标称嵌入式 MTP 2.23× 文本生成 |
| `--jinja` | — | 使用 GGUF 内嵌的 Qwen3.8 chat template。**必须加**，否则 `/v1/chat/completions` 的对话格式不对（我们的 mutator/judge 全靠对话 API） |

### 不需要设的（说明为什么）
- `--mmproj` / 视觉投影器：纯文本红队用不上，mmproj 那个 931MB 文件**不用下载**
- KV cache 量化（`-ctk/-ctv`）：这类 flag 通常要求开 flash-attn，我们在 Volta 上关了 FA，别用
- `--no-mmap`：显存够时无意义，默认即可
- 采样参数（temperature 等）：由每次 API 请求自带，服务端不用设

## 三、量化版本怎么选（对照表）

| 量化 | 文件大小 | 每卡占用 | 建议 -c | 结论 |
|---|---|---|---|---|
| **Q5_K_P** | 20.2GB | ~10.1GB | 32768 | ★ 推荐：质量最优档（K_P 系列比同号普通版好一档），显存够 |
| Q4_K_P | 17.9GB | ~9.0GB | 32768~49152 | 也很好；想开 48K 上下文或给 2B 检测器腾 GPU 时选它 |
| IQ4_XS | 15.7GB | ~7.9GB | 49152+ | 显存余量最大，质量略降 |
| Q6_K_P | 25.9GB | ~13.0GB | ≤16384 | 每卡太满，上下文被挤小，**不推荐** |
| Q8_K_P | 31.5GB | 15.7GB | 装不下 | 双卡 32G 放不下 |

KV cache 估算：Qwen3.8-27B 是混合架构（48 个线性层不吃 KV，16 个注意力层），
32K 上下文 KV 约 2GB（两卡分摊各 1GB），Q5_K_P 下每卡 10.1+1+缓冲 ≈ 11.5GB < 16GB，安全。

**你已下载哪个量化就直接用哪个**（文件名里的 `Q5_K_P`/`IQ4_XS` 等字样），差别主要在
质量-显存取舍；已下载 Q4 系列完全没问题。

## 四、FastMTP-32K.gguf（那个 903MB 的文件）要不要加？

**两条加速路线，二选一：**

### 路线 A：内嵌 MTP（上面的命令，推荐先用）
- 用主 GGUF 自带的 MTP 头，`--spec-type draft-mtp` 一个 flag 搞定
- **不需要** FastMTP-32K.gguf，不需要打补丁
- 提速：文档标称 ~2.2× 文本生成

### 路线 B：FastMTP sidecar（追求 3× 时再上）
1. 编译带补丁的 llama.cpp（一次性，约 10 分钟）：
```bash
cd ~/llama.cpp    # 你克隆的 llama.cpp 目录
curl -L -o fastmtp.patch \
  "https://huggingface.co/HauhauCS/Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-MTP-GGUF/resolve/main/HauhauCS-FastMTP-llama.cpp.patch"
git apply fastmtp.patch
cmake -S . -B build -DGGML_CUDA=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j$(nproc)
```
2. 下载 sidecar：`Qwen3.8-27B-Uncensored-HauhauCS-Aggressive-FastMTP-32K.gguf`（903MB）
3. 启动命令在路线 A 基础上按模型仓库 README「Run HauhauCS FastMTP」小节加 draft
   模型参数（`-md <FastMTP-32K.gguf>` 一族 flag，以 README 为准）
4. 标称收益：比内嵌 MTP 再快 ~20-35%，最高 3× 文本生成

**建议**：先用路线 A 跑通整个评估流程；确认值得再上路线 B（同样的评估会快一半左右）。

## 四点五、AMD GPU（ROCm）单卡部署 —— 以 RX 9070 XT 17GB 为例

`setup_env.sh` 已自动检测：机器有 `rocm-smi` 就用 **HIP 后端**构建
（自动带 `-DAMDGPU_TARGETS=gfx1201` 这类目标）；`serve_attacker.sh` 自动识别单卡
（不再加 tensor-split）。手动强制后端：`LLAMA_BACKEND=hip|cuda|vulkan|cpu bash setup_env.sh`。

**17GB 单卡量化选型**（27B）：

| 量化 | 大小 | 可行性 |
|---|---|---|
| **IQ3_M（推荐）** | 12.8GB | ✓ 剩余空间放 KV(16-24K ctx)+缓冲 |
| Q3_K_P | 13.4GB | ✓ 刚好（16K ctx） |
| IQ4_XS | 15.7GB | ✗ KV 挤不进（除非 4K ctx，太小） |
| Q4_K_P+ | 17.9GB | ✗ 放不下 |

```bash
# 构建（自动 HIP）+ 下载适配量化的模型：
LLAMA_BACKEND=hip bash setup_env.sh          # 或不设变量让它自动检测
QUANT=IQ3_M CTX=16384 bash download_model.sh
bash serve_attacker.sh                        # 单卡自动不加 tensor-split
```

- Volta 关 flash-attn 的经验对 RDNA4 同样适用：保持 `FA=0`
- 若 HIP 构建有兼容问题（RDNA4 较新），退路是 **Vulkan 后端**：
  `LLAMA_BACKEND=vulkan bash setup_env.sh`（RDNA4 的 Vulkan 支持很好）
- 本机就是"单机模式"全套：27B attacker + victim(CPU) + 检测器(CPU) + runner 全在这台机器
- 显存预估：IQ3_M 权重 12.8GB + KV 16K ≈1GB + 缓冲 ≈1GB ≈ **15GB < 17GB** ✓

## 五、启动后怎么验证（3 条命令）

```bash
# 1. 模型在线 + 名字对不对（id 要填进 config.yaml 的 model:）
curl -s http://127.0.0.1:8000/v1/models

# 2. 能不能正常对话（应返回一段 JSON，content 里有回复）
curl -s http://127.0.0.1:8000/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"Qwen3.8-27B-Uncensored-Aggressive","messages":[{"role":"user","content":"用一句话介绍你自己"}],"max_tokens":50}'

# 3. 项目体检（在 ~/ams-redteam/remote 下）
bash run_eval.sh --dry-run    # Mutator/Judge/Critic 应全 OK
```

## 六、与 config.yaml 的对应关系

| llama-server 参数 | config.yaml 字段 |
|---|---|
| `--port 8000` | `attacker/critic/judge` 的 `base_url: "http://127.0.0.1:8000/v1"` |
| `--alias`（或 /v1/models 的 id） | 三处的 `model:` |

如果你沿用别的端口（比如默认 8080）或没设 alias，就把 config.yaml 三处改成实际值。

## 七、常见问题

| 症状 | 原因/解决 |
|---|---|
| `unknown argument: --spec-type` | llama.cpp 太旧：删掉该 flag 先跑，或重新编译最新版 |
| 启动即崩 / CUDA error | flash-attn 没关（Volta）→ 确认 `--flash-attn 0` |
| CUDA OOM | 降量化（Q5_K_P→Q4_K_P）或减 `-c`（32768→16384） |
| mutator 输出 JSON 被截断 | `-c` 太小或 `--parallel` 太多把每 slot 上下文挤小了；-c ≥ 32768 |
| 对话回复格式怪/不遵循指令 | 没加 `--jinja` |
| 一块卡闲着 | 没加 `--tensor-split 0.5,0.5` 和 `-ngl 999` |

---

*本文件在项目仓库 `remote/LLAMA-SERVER.md`；V100 上 `git pull` 即可获取。*

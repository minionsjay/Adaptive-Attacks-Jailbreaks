# 专利申请可行性分析与实现路线图

> 基于：5673 行代码、9 个 Guard、7 轮 victim 实验、258+ 条候选数据、
> 8 个已验证的创新点、以及 2025-2026 年最新文献调研。
> 分析哪些能申请专利、每个需要额外做什么、工作量预估。

---

## 一、专利拆分方案：3 件发明专利

### 专利一（核心方法）：多语言自适应进化攻击生成方法

**覆盖创新点**：① 多语言 3D 进化空间 + ② 双层判定机制 + ④ 共识种子筛选

**当前实现度**：**95%**——代码已全部写好并验证过

| 组件 | 实现状态 | 还差什么 |
|---|---|---|
| MAP-Elites 多岛进化 | ✅ 已实现（controller.py） | 无 |
| 15 语言变体维度 | ✅ 已实现（strategies.py） | 无 |
| 双层判定（Judge + 可操作性校验） | ✅ 已实现（jailbreak.py） | 无 |
| 共识种子预筛选 | ✅ 已实现（prescreen_seeds.py） | 无 |
| 灵感组合公式 | ✅ 已实现（controller.py） | 无 |
| 实验数据 | ✅ 4 轮 × 4 Guard × 60+ 条/轮 | 需补充：严格 Judge 全量重判 |

**还需要做的**：
1. [ ] 用严格 Judge 重判全部 258 条（脚本已有 rejudge.py，需跑完）
2. [ ] 补充 1-2 张流程图/架构图（用于专利附图）
3. [ ] 请专利代理人写正式权利要求书
4. [ ] 时间：**1-2 周可提交**

**预期保护范围**：四步进化循环方法本身 + 多语言维度 + 双层判定 + 共识筛选

---

### 专利二（检测器改进）：基于自校准阈值的安全检测器系统与真实误报率评估方法

**覆盖创新点**：③ 自校准 PPL 检测器 + ⑤ 真实误报率探测（区分实验 FP vs 真实 FPR）+ ⑧ 统一多 Guard 评估协议

**当前实现度**：**80%**——核心代码已写好，需补充系统化验证

| 组件 | 实现状态 | 还差什么 |
|---|---|---|
| 自校准 PPL 检测器 | ✅ 已实现（serve_detector.py） | 需在更多语言/模型上验证 |
| 真实误报率探测 | ✅ 已实现（probe_fpr.py） | 需扩大良性样本集 |
| 统一多 Guard 评估协议 | ✅ 已实现（serve_detector.py + registry.py） | 无 |
| 归一化管道 | ✅ 已实现（keyword_baseline.py v2） | 可扩展更多语言 |
| 实验数据 | ✅ 9 Guard × 79 种子预筛选 + 30 条良性探测 | 需扩大规模 |

**还需要做的**：
1. [ ] 在至少 3 种语言上验证自校准 PPL 的阈值稳定性
2. [ ] 将良性探测样本扩大到 100+ 条（当前仅 30 条）
3. [ ] 与固定阈值方法做正式消融对比（证明自校准优于固定阈值）
4. [ ] 时间：**2-3 周可提交**

**预期保护范围**：自校准方法 + 统一评估协议 + 误报率探测方法

---

### 专利三（闭环系统）：进化-防御联合对抗训练与数据回流系统

**覆盖创新点**：⑥ 攻防闭环数据回流 + ⑦ XAI 引导攻击 + ⑨ 跨语言鸿沟利用 + ⑩ 表示空间安全度量

**当前实现度**：**40%**——框架和数据回流已实现，但核心算法（XAI 引导/表示空间度量/联合训练）未实现

| 组件 | 实现状态 | 还差什么 |
|---|---|---|
| 数据回流（bypass→训练数据） | ✅ 已实现（store.py + verify_jailbreaks.py） | 需接通实际的检测器微调流程 |
| 人工核验工具 | ✅ 已实现（verify_jailbreaks.py） | 需补充自动预筛准确率验证 |
| XAI 引导攻击生成 | ❌ 未实现 | 需集成 SHAP/IntegratedGradients |
| 表示空间安全度量 | ❌ 未实现 | 需获取 victim 模型的中间层隐藏状态 |
| 跨语言鸿沟利用 | ❌ 未实现 | 需多语言安全分数量化模块 |
| 实验数据 | ⚠️ 部分有（严格版实验中 0 绕过 = victim 太强） | 需在更弱的 victim 上验证 |

**还需要做的**：
1. [ ] 实现 XAI 引导：集成 SHAP 分析 Guard 的 token 级归因 → 定向变异
2. [ ] 实现表示空间度量：获取 victim 中间层隐藏状态 → 计算与有害参考向量的距离
3. [ ] 实现联合训练：用回流数据对 deberta/piguard 做 LoRA 微调 → 验证改进效果
4. [ ] 在 R1-Distill-1.5B（弱 victim）上验证——qwen3-max 太强打不穿
5. [ ] 时间：**4-6 周**（需要实际编码 + 实验 + 数据分析）

**预期保护范围**：XAI 引导攻击生成方法 + 表示空间安全度量方法 + 联合对抗训练闭环

---

## 二、实现路线图

```
第 1 周（专利一收尾）:
├── Day 1-2: 用 rejudge.py 重判 258 条（严格标准）
├── Day 3-4: 生成对比图表（初始拦截率 vs 进化后拦截率）
├── Day 5: 写技术交底书正式版
└── 提交专利一申请 ✓

第 2-3 周（专利二验证）:
├── 在 3 种语言上测试自校准 PPL 阈值稳定性
├── 扩大良性探测样本到 100+
├── 做自校准 vs 固定阈值的消融对比
├── 写技术交底书
└── 提交专利二申请 ✓

第 4-8 周（专利三核心算法实现）:
├── Week 4-5: 实现 XAI 引导（SHAP → 变异器提示注入）
├── Week 5-6: 实现表示空间度量（victim 中间层隐藏状态提取）
├── Week 6-7: 在 R1-Distill-1.5B 上跑联合训练实验
├── Week 8: 写技术交底书 + 提交
└── 提交专利三申请 ✓
```

---

## 三、代码实现清单（专利三需要的核心代码）

### 3.1 XAI 引导攻击生成（预计 200 行）

```python
# 新文件: ams/xai_guide.py
# 功能: 分析 Guard 的 token 级归因，提取敏感模式，注入变异器提示

class XAIGuide:
    def __init__(self, guard_model_id):
        """加载 Guard 模型用于归因分析"""
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        from captum.attr import IntegratedGradients  # pip install captum
        
    def get_token_attributions(self, text) -> dict:
        """返回每个 token 的归因分数 {token: attribution_score}"""
        # 用 IntegratedGradients 计算
        
    def get_sensitive_patterns(self, n_samples=50) -> list:
        """统计被拦截样本的高归因 token → 提取 Guard 的敏感模式"""
        # 对 n_samples 条被拦截样本做归因 → 聚合高频高归因 token
        
    def generate_bypass_hint(self) -> str:
        """生成绕过提示注入变异器"""
        # "Guard 对以下 token/模式高度敏感: [列表]
        #  请在变异时避免这些模式，替换为语义相似的表达"
```

### 3.2 表示空间安全度量（预计 150 行）

```python
# 新文件: ams/representation_safety.py
# 功能: 获取 victim 中间层隐藏状态 → 计算与有害参考向量的距离

class RepresentationSafety:
    def __init__(self, victim_model, harm_ref_vectors):
        """victim_model: HF 模型; harm_ref_vectors: 有害样本的隐藏状态中心"""
        
    def get_hidden_state(self, text) -> torch.Tensor:
        """获取 victim 对 text 的中间层隐藏状态"""
        # hook 到最后 transformer 层
        
    def safety_score(self, text) -> float:
        """0=安全(离有害远) 1=已偏向有害(离有害近)"""
        # cosine_similarity(hidden_state, harm_ref_vectors).max()
        
    def build_harm_reference(self, known_harmful_texts) -> torch.Tensor:
        """从已知有害样本构建有害参考向量中心"""
```

### 3.3 联合训练闭环（预计 100 行）

```python
# 新文件: ams/joint_training.py
# 功能: 用回流数据对检测器做 LoRA 微调

class JointTrainer:
    def __init__(self, detector_model_id, lora_rank=8):
        """加载检测器 + 配置 LoRA"""
        from peft import LoraConfig, get_peft_model
        
    def fine_tune(self, training_data_path, epochs=3):
        """用回流数据微调检测器"""
        # 标准 SFT 流程
        
    def evaluate_improvement(self, test_attacks) -> dict:
        """微调后重新评估 → 对比微调前后的拦截率"""
```

### 3.4 实验流程整合

```python
# 修改: ams/harness.py
# 在每代评估后加入:
# 1. 如果有绕过样本 → 触发数据回流 → 微调检测器
# 2. 微调后的检测器 → 重新评估 → 观察改进
# 3. 用表示空间度量 → 发现"准绕过"

# 伪代码:
for gen in range(max_gens):
    # 现有流程：propose → score → select → update
    ...
    
    # 新增：如果发现绕过样本
    if bypass_count > 0:
        # 数据回流
        trainer.fine_tune(export_training_data())
        
        # 重新评估旧种子
        old_detection_rate = evaluate_on_seeds(updated_detector)
        print(f"检测器微调后拦截率: {old_detection_rate:.0%}")
```

---

## 四、专利与论文的双轨策略

```
        时间线 ──────────────────────────────────────→
        
专利一 ──── [提交] ─────────────────────────────────────→
             │
论文 ──────  │ ──── [投稿] ──── [发表] ─────────────────→
             │         │
专利二 ──────┼─────────┼──── [提交] ─────────────────────→
             │         │        │
专利三 ──────┼─────────┼────────┼──── [提交] ─────────→
             │         │        │
关键：论文发表日期必须在专利提交日之后
     论文中引用自己的专利申请号："本方法已申请中国发明专利（申请号：XXXX）"
```

---

## 五、成本预估

| 项目 | 费用 |
|---|---|
| 发明专利申请费（3件） | ¥2,000-4,500（官费，可申请减缴至 ¥500-1,500）|
| 专利代理人服务费（3件） | ¥15,000-30,000 |
| 论文投稿版面费（可选） | ¥0-5,000（视会议/期刊）|
| GPU/API 成本（补充实验） | ¥0-500（用现有设备+免费额度）|
| **总计** | **¥20,000-40,000**（3 件专利 + 1 篇论文）|

---

## 六、每个专利的核心卖点（一句话）

| 专利 | 一句话卖点 |
|---|---|
| 专利一 | "首次将多语言变体引入 MAP-Elites 进化攻击，通过双层判定机制解决 LLM 裁判假阳性问题" |
| 专利二 | "首个自校准安全检测器——无需人工设定阈值，自动适配任意语言和场景" |
| 专利三 | "首个攻防闭环系统——进化攻击发现的漏洞自动转化为检测器训练数据，形成持续改进闭环" |

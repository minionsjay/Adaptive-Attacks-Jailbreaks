# -*- coding: utf-8 -*-
"""
controller.py — MAP-Elites 岛模型进化控制器（论文搜索方法的工程实现）

论文设定（第 4.3 节）：
- 候选按两个行为属性量化入网格：
    ① trigger 字符长度（10 个 bin，对数分档）
    ② 多样性 = 与随机 elite 的平均归一化编辑距离（10 个 bin）
- 5 个岛轮转使用，每格只留最高适应度 elite
- 每步喂给变异器的灵感组合 = 当前最佳 + 3 随机 elite + 邻近 bin 的 5 个 elite + 库中 5 个随机候选

质量维(fitness)由 oracle 判定；行为维只看"长什么样"，不看"好不好"，
这保证搜索不会在单一形态的局部最优上坍缩——论文能推高 ASR 的关键设计。
"""
import random
from .types import AttackCandidate


# ---------- 编辑距离（用于多样性度量）----------
def levenshtein(a, b, cap=256):
    """带长度截断的编辑距离（防超长串拖慢）"""
    a, b = a[:cap], b[:cap]
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1,          # 删除
                           cur[j - 1] + 1,       # 插入
                           prev[j - 1] + (ca != cb)))  # 替换
        prev = cur
    return prev[-1]


def norm_edit_distance(a, b):
    n = max(len(a), len(b), 1)
    return min(1.0, levenshtein(a, b) / n)


# ---------- 行为属性 → bin ----------
LENGTH_BINS = [0, 17, 33, 65, 129, 257, 513, 1025, 2049, 4097]  # 10 档对数边界


def length_bin(trigger: str) -> int:
    n = len(trigger or "")
    for i in range(len(LENGTH_BINS) - 1, -1, -1):
        if n >= LENGTH_BINS[i]:
            return i
    return 0


def diversity_bin(div: float) -> int:
    """div ∈ [0,1] → 10 档"""
    return min(9, max(0, int(div * 10)))


class Island:
    """一个 MAP-Elites 岛：10×10 网格，每格一个最高适应度 elite"""

    def __init__(self, island_id):
        self.id = island_id
        self.grid = {}          # (len_bin, div_bin) -> AttackCandidate
        self.best = None        # 本岛历史最佳

    def add(self, cand: AttackCandidate):
        key = (cand._len_bin, cand._div_bin)
        cur = self.grid.get(key)
        if cur is None or cand.fitness > cur.fitness:
            self.grid[key] = cand
        if self.best is None or cand.fitness > self.best.fitness:
            self.best = cand
        return key in self.grid and self.grid[key] is cand

    def elites(self):
        return list(self.grid.values())

    def neighbors(self, cand, radius=1, limit=5):
        """取 (len_bin±1, div_bin±1) 邻格的 elite（论文：邻近 bin 灵感）"""
        lb, db = cand._len_bin, cand._div_bin
        out = []
        for dl in range(-radius, radius + 1):
            for dd in range(-radius, radius + 1):
                if dl == 0 and dd == 0:
                    continue
                c = self.grid.get((lb + dl, db + dd))
                if c:
                    out.append(c)
        random.shuffle(out)
        return out[:limit]

    @property
    def size(self):
        return len(self.grid)


class MAPElitesController:
    """多岛 MAP-Elites 控制器 + 全局候选池"""

    def __init__(self, n_islands=5, pool_capacity=400, n_ref_elites=25):
        self.n_islands = n_islands
        self.islands = [Island(i) for i in range(n_islands)]
        self.pool = []                 # 全体评估过的候选（供随机灵感与多样性参照）
        self.pool_capacity = pool_capacity
        self.n_ref_elites = n_ref_elites
        self.best = None               # 全局历史最佳
        self._island_cursor = 0

    # ---------- 主体 ----------
    def next_island(self) -> Island:
        isl = self.islands[self._island_cursor % self.n_islands]
        self._island_cursor += 1
        return isl

    def add(self, cand: AttackCandidate):
        """评估完成后入库：算行为 bin → 岛网格 + 全局池"""
        # 多样性 = 与随机 elite 的平均归一化编辑距离
        refs = random.sample(self.pool, min(self.n_ref_elites, len(self.pool))) \
            if self.pool else []
        if refs:
            div = sum(norm_edit_distance(cand.trigger or cand.prompt, r.trigger or r.prompt)
                      for r in refs) / len(refs)
        else:
            div = 0.5
        cand._len_bin = length_bin(cand.trigger or cand.prompt)
        cand._div_bin = diversity_bin(div)
        cand._diversity = round(div, 4)

        isl = self.islands[cand.island % self.n_islands]
        isl.add(cand)

        self.pool.append(cand)
        if len(self.pool) > self.pool_capacity:
            # 淘汰适应度最低的半区（保留成功样本防丢）
            self.pool.sort(key=lambda c: -c.fitness)
            keep = max(self.pool_capacity // 2,
                       sum(1 for c in self.pool if c.success))
            self.pool = self.pool[:max(keep, self.pool_capacity // 2)]

        if self.best is None or cand.fitness > self.best.fitness:
            self.best = cand
        return cand

    # ---------- 灵感组合（论文：best + 随机 elite + 邻近 bin + 随机池）----------
    def inspiration_set(self, island: Island, n=8):
        picked, seen = [], set()

        def take(c):
            if c and c.id not in seen:
                seen.add(c.id)
                picked.append(c)

        take(self.best)                                    # 当前最佳
        for c in random.sample(island.elites(),
                               min(3, island.size)):       # 3 个随机 elite
            take(c)
        if island.best is not None:                        # 邻近 bin 的 5 个
            for c in island.neighbors(island.best):
                take(c)
        for c in random.sample(self.pool, min(5, len(self.pool))):  # 池中 5 个随机
            take(c)
        return picked[:n]

    def languages_covered(self):
        return {c.language for c in self.pool}

    @property
    def archive_size(self):
        return sum(i.size for i in self.islands)

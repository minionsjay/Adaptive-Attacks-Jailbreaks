# -*- coding: utf-8 -*-
"""
AMS-RedTeam 核心包
《The Attacker Moves Second》(USENIX Security 2026) 自适应攻击框架的工程实现。

Propose(提出) → Score(打分) → Select(选择) → Update(更新) 四步循环，
以 MAP-Elites 岛模型进化搜索为核心，对越狱/提示注入检测器做强自适应评估。
"""

__version__ = "1.0.0"

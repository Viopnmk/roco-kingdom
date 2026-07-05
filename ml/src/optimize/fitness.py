"""
多目标适应度函数 — 对一支6精灵队伍打分

目标 (按重要性):
  1. 打击面覆盖 — 18属性至少能打≥1x，方差惩罚
  2. 抗性互补 — 无共同≥2x弱点
  3. 联动得分 — 队内精灵对之间的平均联动分
  4. 有效种族值 — 物攻/魔攻有效利用率
  5. 职责平衡 — 输出:坦克:辅助比例
  6. 速度梯度 — 速度分布适中
  7. 能量平衡 — 平均能耗不能太高
"""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from collections import Counter

TYPES = [
    "普通", "草", "火", "水", "光", "地", "冰", "龙",
    "电", "幻", "毒", "虫", "翼", "恶", "萌", "幽灵", "武", "机械",
]


class TeamFitness:
    """7维适应度计算器。"""

    def __init__(
        self,
        profiles: List[dict],
        synergy_pairs: List[dict],
        type_chart: dict,
    ):
        self.profiles: Dict[int, dict] = {p["id"]: p for p in profiles}
        self.synergy: Dict[Tuple[int, int], float] = {}
        for pair in synergy_pairs:
            a, b = pair["pet_a_id"], pair["pet_b_id"]
            self.synergy[(min(a, b), max(a, b))] = pair["score"]
        self.type_chart = type_chart
        self._id_list = list(self.profiles.keys())

    # ── Objective 1: Coverage ─────────────────────────────────────
    def coverage_score(self, team: List[Tuple[int, List[str]]]) -> float:
        """团队打击面得分: 覆盖度+最大克制倍率。"""
        team_cov: Dict[str, float] = {}
        for pid, _ in team:
            pet = self.profiles.get(pid)
            if not pet:
                continue
            for def_type, mult in pet.get("coverage_vector", {}).items():
                team_cov[def_type] = max(team_cov.get(def_type, 0), mult)

        scores = []
        for def_type in TYPES:
            m = team_cov.get(def_type, 1.0)
            scores.append(m)

        mean_cov = np.mean(scores)
        var_penalty = np.var(scores) * 0.1  # 方差大（部分属性覆盖不足）扣分
        blank_penalty = sum(1 for s in scores if s <= 1.0) * 2  # 打不出克制的属性每个扣2分
        return mean_cov * 10 - var_penalty - blank_penalty

    # ── Objective 2: Defense Synergy ──────────────────────────────
    def defense_score(self, team: List[Tuple[int, List[str]]]) -> float:
        """抗性互补得分: 共同弱点越少越好。"""
        weaknesses: List[set] = []
        for pid, _ in team:
            pet = self.profiles.get(pid)
            if not pet:
                continue
            weak_set = set()
            for atk_type, mult in pet.get("weakness_vector", {}).items():
                if mult >= 2.0:
                    weak_set.add(atk_type)
            weaknesses.append(weak_set)

        score = 10.0
        # 检查每对精灵的共享弱点
        n = len(weaknesses)
        for i in range(n):
            for j in range(i + 1, n):
                shared = weaknesses[i] & weaknesses[j]
                if shared:
                    score -= 3 * len(shared)  # 每共享一个弱点 -3
        return max(0, score)

    # ── Objective 3: Synergy ──────────────────────────────────────
    def synergy_score(self, team: List[Tuple[int, List[str]]]) -> float:
        """队内联动得分: 所有精灵对之间的平均联动分。"""
        pairs = 0
        total = 0.0
        n = len(team)
        for i in range(n):
            for j in range(i + 1, n):
                key = (min(team[i][0], team[j][0]), max(team[i][0], team[j][0]))
                total += self.synergy.get(key, 0)
                pairs += 1
        return total / pairs if pairs > 0 else 0

    # ── Objective 4: Effective Stats ──────────────────────────────
    def stats_score(self, team: List[Tuple[int, List[str]]]) -> float:
        """有效种族值利用率: 每只精灵的 effective damage stat / total。"""
        total = 0.0
        for pid, _ in team:
            pet = self.profiles.get(pid)
            if not pet:
                continue
            eff = max(pet.get("effective_atk", 0), pet.get("effective_sp_atk", 0))
            tot = pet.get("stat_total", 300)
            total += eff / tot if tot > 0 else 0
        return total / len(team) * 100  # 缩放到合理范围

    # ── Objective 5: Role Balance ─────────────────────────────────
    def role_score(self, team: List[Tuple[int, List[str]]]) -> float:
        """职责平衡: 理想比例 输出:坦克:辅助 = 3:2:1。"""
        roles = []
        for pid, _ in team:
            pet = self.profiles.get(pid)
            if not pet:
                continue
            r = pet.get("role", "一般")
            if r in ("物理输出", "魔法输出", "双刀", "高速游击"):
                roles.append("attacker")
            elif r == "坦克":
                roles.append("tank")
            elif r in ("辅助", "控场", "天气手"):
                roles.append("support")
            else:
                roles.append("attacker")  # 默认算输出

        counts = Counter(roles)
        a = counts.get("attacker", 0)
        t = counts.get("tank", 0)
        s = counts.get("support", 0)

        # 理想: 3/2/1
        target = np.array([3, 2, 1])
        actual = np.array([a, t, s])
        # 余弦相似度
        dot = np.dot(target, actual)
        norm = np.linalg.norm(target) * np.linalg.norm(actual)
        return (dot / norm) * 10 if norm > 0 else 0

    # ── Objective 6: Speed Gradient ───────────────────────────────
    def speed_score(self, team: List[Tuple[int, List[str]]]) -> float:
        """速度梯度: 不要太集中（方差适中），不要太极端。"""
        speeds = []
        for pid, _ in team:
            pet = self.profiles.get(pid)
            if pet:
                speeds.append(pet.get("stat_speed", 80))
        if not speeds:
            return 5
        var = np.var(speeds)
        # 理想方差 ~200（不要太集中也别太散）
        return max(0, 10 - abs(var - 200) / 50)

    # ── Objective 7: Energy Balance ───────────────────────────────
    def energy_score(self, team: List[Tuple[int, List[str]]]) -> float:
        """能量平衡: 总平均能耗不能太高。"""
        total = 0.0
        for pid, _ in team:
            pet = self.profiles.get(pid)
            if pet:
                total += pet.get("avg_energy_cost", 3)
        avg = total / len(team)
        return max(0, 10 - abs(avg - 3.0) * 2)

    # ── Full fitness vector ───────────────────────────────────────
    def evaluate(self, team: List[Tuple[int, List[str]]]) -> Tuple[float, ...]:
        """返回7维适应度向量。"""
        return (
            self.coverage_score(team),
            self.defense_score(team),
            self.synergy_score(team),
            self.stats_score(team),
            self.role_score(team),
            self.speed_score(team),
            self.energy_score(team),
        )

    def total_score(self, team: List[Tuple[int, List[str]]],
                    weights: Tuple[float, ...] = (3, 3, 2, 1.5, 1, 0.5, 0.5),
                    team_type: Optional[str] = None) -> float:
        """加权总分。"""
        # 体系队: 联动↑ 种族值↑ 打击面↓ 抗性↓
        # 平衡队: 打击面↑ 抗性↑ 联动↓
        if team_type == "synergy":
            w = (1.5, 1.5, 5.0, 2.0, 1.0, 0.5, 0.5)
        elif team_type == "balanced":
            w = (4.0, 4.0, 0.5, 1.5, 1.0, 0.5, 0.5)
        else:
            w = weights
        v = self.evaluate(team)
        return sum(w_i * vi for w_i, vi in zip(w, v))

    # ── Constraint check ──────────────────────────────────────────
    def check_constraints(
        self,
        team: List[Tuple[int, List[str]]],
        must_include: Optional[List[int]] = None,
        must_exclude: Optional[List[int]] = None,
        prefer_type: Optional[str] = None,
        style: Optional[str] = None,
        team_type: Optional[str] = None,
        min_coverage: float = 0.0,
    ) -> bool:
        """检查团队是否满足约束。进化链不作为硬约束——由引导变异自然收敛。"""
        team_ids = {pid for pid, _ in team}

        if must_include:
            if not all(mid in team_ids for mid in must_include):
                return False

        if must_exclude:
            if any(eid in team_ids for eid in must_exclude):
                return False

        if prefer_type:
            type_count = sum(
                1 for pid in team_ids
                if self.profiles.get(pid, {}).get("type_primary") == prefer_type
                or self.profiles.get(pid, {}).get("type_secondary") == prefer_type
            )
            if type_count < 1:
                return False

        if style:
            # 战术风格要求: 至少2只有该战术簇标签
            style_tags = {
                "灼烧体系": "灼烧", "中毒消耗": "中毒", "冻结控场": "冻结",
                "星陨爆发": "星陨", "天气队": "天气", "传动体系": "传动",
                "印记运营": "印记", "应对返还": "应对攻击",
                "先手压制": "先手", "吸血续航": "吸血",
                "增益传递": "增益传递", "巧变切换": "巧变",
                "萌化退化": "萌化",
            }
            tag = style_tags.get(style, style)
            tagged = sum(
                1 for pid in team_ids
                if tag in self.profiles.get(pid, {}).get("synergy_tags", [])
            )
            if tagged < 2:
                return False

        # ── 配队类型约束 ──
        if team_type == "synergy":
            # 体系队: 至少3只共享主属性（单属性核心）
            type_counter = Counter()
            for pid in team_ids:
                pet = self.profiles.get(pid, {})
                tp = pet.get("type_primary", "")
                if tp:
                    type_counter[tp] += 1
            if max(type_counter.values(), default=0) < 3:
                return False

        elif team_type == "balanced":
            # 平衡队: 任意主属性不超过2只（属性分散）
            type_counter = Counter()
            for pid in team_ids:
                pet = self.profiles.get(pid, {})
                tp = pet.get("type_primary", "")
                if tp:
                    type_counter[tp] += 1
            if max(type_counter.values(), default=0) > 2:
                return False

            # 平衡队: 总共享弱点对数 ≤ 3（允许少量重叠）
            weakness_sets = []
            for pid in team_ids:
                pet = self.profiles.get(pid, {})
                weak_set = set()
                for atk_type, mult in pet.get("weakness_vector", {}).items():
                    if mult >= 2.0:
                        weak_set.add(atk_type)
                weakness_sets.append(weak_set)
            total_shared = 0
            n = len(weakness_sets)
            for i in range(n):
                for j in range(i + 1, n):
                    total_shared += len(weakness_sets[i] & weakness_sets[j])
            if total_shared > 3:
                return False

        if min_coverage > 0:
            cov = self.coverage_score(team)
            if cov < min_coverage:
                return False

        return True


def load_fitness_engine() -> TeamFitness:
    """加载适应度引擎（使用预计算的数据文件）。"""
    base = Path(__file__).resolve().parents[3]

    with open(base / "ml" / "data" / "pet_profiles.json", "r", encoding="utf-8") as f:
        profiles = json.load(f)
    with open(base / "ml" / "data" / "synergy_graph.json", "r", encoding="utf-8") as f:
        synergy_data = json.load(f)
    with open(base / "scraper" / "output" / "type_chart.json", "r", encoding="utf-8") as f:
        type_chart = json.load(f)["chart"]

    return TeamFitness(profiles, synergy_data["pairs"], type_chart)


if __name__ == "__main__":
    engine = load_fitness_engine()
    # 测试随机队伍
    import random
    ids = engine._id_list
    test_team = [(random.choice(ids), ["一拳", "丢冰块", "冬至", "充分燃烧"]) for _ in range(6)]
    scores = engine.evaluate(test_team)
    print(f"测试队伍分数: coverage={scores[0]:.1f} defense={scores[1]:.1f} "
          f"synergy={scores[2]:.1f} stats={scores[3]:.1f} "
          f"role={scores[4]:.1f} speed={scores[5]:.1f} energy={scores[6]:.1f}")
    print(f"总分: {engine.total_score(test_team):.1f}")

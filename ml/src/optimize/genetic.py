"""
NSGA-II 多目标遗传算法 — 搜索最优6精灵配队

核心参数:
  - 种群: 300, 代数: 200
  - 交叉: 队伍间交换精灵
  - 变异: 随机替换精灵 / 技能替换
  - 精英保留: Top 10%

候选池: 266只顶端精灵（进化链顶端 + 独立精灵），数据层已过滤，算法无需关注进化。

用户约束: must_include / must_exclude / prefer_type / style / min_coverage
"""

import json
import random
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass, field

from .fitness import TeamFitness, load_fitness_engine

# ── 算法参数 ──────────────────────────────────────────────────────

POP_SIZE = 300
GENERATIONS = 200
ELITE_RATE = 0.10
CROSSOVER_RATE = 0.80
MUTATION_RATE = 0.15
TOURNAMENT_SIZE = 3

# ── 个体表示 ──────────────────────────────────────────────────────

# 染色体: [(pet_id, [skill1..4]), ... x6]
# 为了方便 NSGA-II，包装为 Individual

@dataclass
class Individual:
    team: List[Tuple[int, List[str]]]
    fitness: Tuple[float, ...] = field(default_factory=lambda: (0,) * 7)
    rank: int = 0
    crowding_distance: float = 0.0


# ── 初始化 ────────────────────────────────────────────────────────

def random_team(
    pet_ids: List[int],
    pet_skills: Dict[int, List[str]],
    must_include: Optional[List[int]] = None,
    must_exclude: Optional[List[int]] = None,
    team_size: int = 6,
) -> List[Tuple[int, List[str]]]:
    """生成随机队伍（无进化链约束，多样性由引导变异负责）。"""
    available = list(pet_ids)
    if must_exclude:
        available = [pid for pid in available if pid not in must_exclude]

    selected_ids: Set[int] = set(must_include or [])

    # 随机填充到 team_size
    remaining = [pid for pid in available if pid not in selected_ids]
    while len(selected_ids) < team_size and remaining:
        pid = random.choice(remaining)
        selected_ids.add(pid)
        remaining = [p for p in remaining if p != pid]

    team = []
    for pid in selected_ids:
        skills = pet_skills.get(pid, [])
        if len(skills) >= 4:
            chosen = random.sample(skills, 4)
        elif skills:
            chosen = skills[:] + [skills[0]] * (4 - len(skills))  # 不足则重复
        else:
            chosen = ["一拳", "丢冰块", "防御", "休息回复"][:4]  # 兜底
        team.append((pid, chosen))

    return team


def init_population(
    n: int,
    pet_ids: List[int],
    pet_skills: Dict[int, List[str]],
    must_include: Optional[List[int]] = None,
    must_exclude: Optional[List[int]] = None,
) -> List[Individual]:
    """初始化种群。"""
    pop = []
    for _ in range(n):
        team = random_team(pet_ids, pet_skills, must_include, must_exclude)
        pop.append(Individual(team=team))
    return pop


# ── NSGA-II 核心 ──────────────────────────────────────────────────

def fast_non_dominated_sort(population: List[Individual]) -> List[List[Individual]]:
    """快速非支配排序。返回 Pareto 前沿列表。"""
    fronts: List[List[Individual]] = [[]]
    n = len(population)

    dominated_by: List[Set[int]] = [set() for _ in range(n)]
    dominates: List[int] = [0] * n

    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            fi = population[i].fitness
            fj = population[j].fitness
            # i dominates j: all objectives >= j AND at least one >
            if all(a >= b for a, b in zip(fi, fj)) and any(a > b for a, b in zip(fi, fj)):
                dominated_by[i].add(j)
            elif all(a <= b for a, b in zip(fi, fj)) and any(a < b for a, b in zip(fi, fj)):
                dominates[i] += 1

    for i in range(n):
        if dominates[i] == 0:
            fronts[0].append(population[i])
            population[i].rank = 0

    fi = 0
    while fronts[fi]:
        next_front = []
        for ind in fronts[fi]:
            for j in dominated_by[population.index(ind)]:
                dominates[j] -= 1
                if dominates[j] == 0:
                    population[j].rank = fi + 1
                    next_front.append(population[j])
        fi += 1
        if next_front:
            fronts.append(next_front)
        else:
            break

    return fronts


def crowding_distance(front: List[Individual]) -> None:
    """计算拥挤距离（同一前沿内的多样性度量）。"""
    if len(front) <= 2:
        for ind in front:
            ind.crowding_distance = float('inf')
        return

    for ind in front:
        ind.crowding_distance = 0.0

    n_obj = len(front[0].fitness)
    for obj_idx in range(n_obj):
        sorted_front = sorted(front, key=lambda x: x.fitness[obj_idx])
        f_min = sorted_front[0].fitness[obj_idx]
        f_max = sorted_front[-1].fitness[obj_idx]
        if f_max == f_min:
            continue

        sorted_front[0].crowding_distance = float('inf')
        sorted_front[-1].crowding_distance = float('inf')

        for i in range(1, len(sorted_front) - 1):
            sorted_front[i].crowding_distance += (
                (sorted_front[i + 1].fitness[obj_idx] - sorted_front[i - 1].fitness[obj_idx])
                / (f_max - f_min)
            )


# ── 遗传操作 ──────────────────────────────────────────────────────

def tournament_select(population: List[Individual], k: int = TOURNAMENT_SIZE) -> Individual:
    """锦标赛选择: 先比rank，同rank比crowding_distance。"""
    candidates = random.sample(population, min(k, len(population)))
    best = candidates[0]
    for c in candidates[1:]:
        if c.rank < best.rank:
            best = c
        elif c.rank == best.rank and c.crowding_distance > best.crowding_distance:
            best = c
    return best


def crossover(
    parent_a: Individual,
    parent_b: Individual,
    pet_ids: List[int],
    pet_skills: Dict[int, List[str]],
) -> Tuple[Individual, Individual]:
    """交叉: 随机交换1-2只精灵。"""
    team_a = list(parent_a.team)
    team_b = list(parent_b.team)

    if random.random() < CROSSOVER_RATE:
        # 选1个随机位置交换
        idx = random.randint(0, 5)
        team_a[idx], team_b[idx] = team_b[idx], team_a[idx]

        # 确保无重复
        ids_a = {pid for pid, _ in team_a}
        ids_b = {pid for pid, _ in team_b}
        if len(ids_a) < 6 or len(ids_b) < 6:
            # 交换失败，回退
            team_a[idx], team_b[idx] = team_b[idx], team_a[idx]

    return Individual(team=team_a), Individual(team=team_b)


def mutate(
    ind: Individual,
    pet_ids: List[int],
    pet_skills: Dict[int, List[str]],
    must_include: Optional[List[int]] = None,
    must_exclude: Optional[List[int]] = None,
) -> Individual:
    """变异: 随机替换一只精灵或一个技能。"""
    team = list(ind.team)
    must_set = set(must_include or [])

    if random.random() < MUTATION_RATE:
        idx = random.randint(0, 5)

        if random.random() < 0.5:
            # ── 随机替换精灵 ──
            if team[idx][0] not in must_set:
                available = [pid for pid in pet_ids
                            if pid not in {t[0] for t in team}
                            and pid not in (must_exclude or [])]
                if available:
                    new_pid = random.choice(available)
                    skills = pet_skills.get(new_pid, [])
                    new_skills = random.sample(skills, 4) if len(skills) >= 4 else skills[:4]
                    team[idx] = (new_pid, new_skills)
        else:
            # ── 替换一个技能 ──
            pid = team[idx][0]
            skills = pet_skills.get(pid, [])
            if len(skills) > 4:
                current = set(team[idx][1])
                alternatives = [s for s in skills if s not in current]
                if alternatives:
                    old_skills = list(team[idx][1])
                    old_skills[random.randint(0, 3)] = random.choice(alternatives)
                    team[idx] = (pid, old_skills)

    return Individual(team=team)


# ── 主循环 ────────────────────────────────────────────────────────

def optimize(
    fitness_engine: TeamFitness,
    pet_ids: List[int],
    pet_skills: Dict[int, List[str]],
    must_include: Optional[List[int]] = None,
    must_exclude: Optional[List[int]] = None,
    prefer_type: Optional[str] = None,
    style: Optional[str] = None,
    team_type: Optional[str] = None,
    min_coverage: float = 0.0,
    top_k: int = 10,
    pop_size: int = POP_SIZE,
    generations: int = GENERATIONS,
    verbose: bool = True,
):
    """
    主搜索函数。

    Returns:
        排名前 top_k 的队伍，含分数分解
    """
    # 初始化
    pop = init_population(pop_size, pet_ids, pet_skills, must_include, must_exclude)

    if verbose:
        print(f"种群: {pop_size}, 代数: {generations}")
        print(f"约束: must_include={must_include}, style={style}")

    for gen in range(generations):
        # 评估
        for ind in pop:
            if not ind.fitness or ind.fitness == (0,) * 7:
                ind.fitness = fitness_engine.evaluate(ind.team)

        # 检查约束
        valid_pop = []
        for ind in pop:
            if fitness_engine.check_constraints(
                ind.team, must_include, must_exclude, prefer_type, style, team_type, min_coverage
            ):
                valid_pop.append(ind)
            else:
                # 重新生成
                ind.team = random_team(pet_ids, pet_skills, must_include, must_exclude)
                ind.fitness = fitness_engine.evaluate(ind.team)
                valid_pop.append(ind)

        pop = valid_pop

        # NSGA-II 排序
        fronts = fast_non_dominated_sort(pop)
        for front in fronts:
            crowding_distance(front)

        # 选择下一代
        elite_count = max(1, int(pop_size * ELITE_RATE))
        new_pop: List[Individual] = []

        # 精英保留
        for front in fronts:
            for ind in front:
                if len(new_pop) < elite_count:
                    new_pop.append(Individual(team=list(ind.team), fitness=ind.fitness))

        # 填充剩余（选择+交叉+变异）
        while len(new_pop) < pop_size:
            parent_a = tournament_select(pop)
            parent_b = tournament_select(pop)
            child_a, child_b = crossover(parent_a, parent_b, pet_ids, pet_skills)
            child_a = mutate(child_a, pet_ids, pet_skills, must_include, must_exclude)
            child_b = mutate(child_b, pet_ids, pet_skills, must_include, must_exclude)
            new_pop.append(child_a)
            if len(new_pop) < pop_size:
                new_pop.append(child_b)

        pop = new_pop

        if verbose and (gen + 1) % 50 == 0:
            best = max(pop, key=lambda x: sum(x.fitness))
            print(f"  第{gen+1}代: 最佳总分={sum(best.fitness):.1f}")

    # 最终评估
    for ind in pop:
        if not ind.fitness or ind.fitness == (0,) * 7:
            ind.fitness = fitness_engine.evaluate(ind.team)
        ind.fitness = fitness_engine.evaluate(ind.team)

    # 重新检查约束并排序
    valid = [ind for ind in pop if fitness_engine.check_constraints(
        ind.team, must_include, must_exclude, prefer_type, style, team_type, min_coverage
    )]

    # 按总分排序
    valid.sort(key=lambda x: -fitness_engine.total_score(x.team, team_type=team_type))

    # 提取 top_k，去重
    results = []
    seen_teams: Set[Tuple[int, ...]] = set()
    for ind in valid:
        team_key = tuple(sorted(pid for pid, _ in ind.team))
        if team_key in seen_teams:
            continue
        seen_teams.add(team_key)

        scores = ind.fitness
        team_info = []
        for pid, skills in ind.team:
            pet = fitness_engine.profiles.get(pid, {})
            team_info.append({
                "pet_id": pid,
                "name": pet.get("name", f"#{pid}"),
                "type_primary": pet.get("type_primary", ""),
                "type_secondary": pet.get("type_secondary"),
                "role": pet.get("role", ""),
                "skills": skills,
                "stats": {
                    "hp": pet.get("stat_hp", 0),
                    "atk": pet.get("stat_atk", 0),
                    "def": pet.get("stat_def", 0),
                    "sp_atk": pet.get("stat_sp_atk", 0),
                    "sp_def": pet.get("stat_sp_def", 0),
                    "speed": pet.get("stat_speed", 0),
                },
            })

        results.append({
            "team": team_info,
            "scores": {
                "coverage": round(scores[0], 1),
                "defense": round(scores[1], 1),
                "synergy": round(scores[2], 1),
                "stats": round(scores[3], 1),
                "role_balance": round(scores[4], 1),
                "speed": round(scores[5], 1),
                "energy": round(scores[6], 1),
                "total": round(fitness_engine.total_score(ind.team, team_type=team_type), 1),
            },
        })

        if len(results) >= top_k:
            break

    if verbose:
        print(f"\n搜索完成: {len(results)} 个最优队伍")

    return results


# ── 主入口 ────────────────────────────────────────────────────────

def main():
    print("=" * 50)
    print("NSGA-II 配队搜索")
    print("=" * 50)

    base = Path(__file__).resolve().parents[3]

    # 加载数据
    with open(base / "ml" / "data" / "pet_profiles.json", "r", encoding="utf-8") as f:
        profiles = json.load(f)
    with open(base / "ml" / "data" / "parsed_skills.json", "r", encoding="utf-8") as f:
        parsed_skills = json.load(f)

    pet_ids = [p["id"] for p in profiles]
    pet_skills: Dict[int, List[str]] = {}
    for p in profiles:
        pet_skills[p["id"]] = p.get("optimal_skills", [])[:]

    engine = load_fitness_engine()

    # 搜索1: 无约束全局最优
    print("\n[Test 1] 全局搜索...")
    results = optimize(engine, pet_ids, pet_skills, top_k=5, pop_size=100, generations=50, verbose=True)

    print("\nTop 5 队伍:")
    for i, r in enumerate(results):
        names = [m["name"] for m in r["team"]]
        s = r["scores"]
        print(f"  #{i+1} {names}")
        print(f"      总分={s['total']:.0f} 打击={s['coverage']:.0f} 抗性={s['defense']:.0f} "
              f"联动={s['synergy']:.0f} 种族值={s['stats']:.0f}")

    # 搜索2: 约束搜索
    print("\n[Test 2] 灼烧体系搜索...")
    results2 = optimize(
        engine, pet_ids, pet_skills,
        style="灼烧体系",
        top_k=5,
        pop_size=100,
        generations=50,
        verbose=True,
    )
    for i, r in enumerate(results2):
        names = [m["name"] for m in r["team"]]
        s = r["scores"]
        print(f"  #{i+1} {names}")
        print(f"      总分={s['total']:.0f} 联动={s['synergy']:.0f}")

    # 保存
    output = {
        "global_best": results,
        "style_burn": results2,
    }
    out_path = base / "ml" / "data" / "optimization_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n保存: {out_path}")


if __name__ == "__main__":
    main()

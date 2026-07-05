"""
精灵画像生成器 — 计算每只精灵的综合特征

输入: pets.json + parsed_skills.json + learnset.json + type_chart.json
输出: ml/data/pet_profiles.json

每只精灵画像:
  - 有效种族值（物攻/魔攻分向）
  - 最优4技能（基于威力+覆盖+匹配度）
  - 打击面向量（18维 × 最大克制倍率）
  - 抗性面向量（18维 × 受伤倍率）
  - 职责分类（物理输出/魔法输出/坦克/辅助/控场/天气手/高速游击）
  - 能量效率
  - 联动标签汇总
"""

import json
from pathlib import Path
from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field, asdict

TYPES = [
    "普通", "草", "火", "水", "光", "地", "冰", "龙",
    "电", "幻", "毒", "虫", "翼", "恶", "萌", "幽灵", "武", "机械",
]
TYPE_IDX = {t: i for i, t in enumerate(TYPES)}


@dataclass
class PetProfile:
    id: int
    name: str
    type_primary: str
    type_secondary: Optional[str]

    # 种族值
    stat_hp: int
    stat_atk: int
    stat_def: int
    stat_sp_atk: int
    stat_sp_def: int
    stat_speed: int
    stat_total: int

    # 有效种族值
    effective_atk: int
    effective_sp_atk: int
    effective_def: int
    effective_sp_def: int
    effective_speed: int
    effective_hp: int

    # 职责分类
    role: str            # 物理输出/魔法输出/双刀/坦克/辅助/控场/天气手/高速游击/一般

    # 攻击倾向
    attack_preference: str  # "physical" / "magical" / "mixed"

    # 最优4技能
    optimal_skills: List[str]

    # 学会的攻击技能数量
    physical_skill_count: int
    magic_skill_count: int
    status_skill_count: int

    # 打击面向量（18维，对每种防御属性的最大克制倍率）
    coverage_vector: Dict[str, float]

    # 抗性面向量（18维，被每种攻击属性攻击的受伤倍率）
    weakness_vector: Dict[str, float]

    # 能量效率
    avg_energy_cost: float
    has_energy_recovery: bool

    # 联动标签汇总（去重）
    synergy_tags: List[str]

    # 原始特性文本
    ability: str


# ── 辅助函数 ──────────────────────────────────────────────────────

def load_json(path: Path) -> dict | list:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def calc_coverage_vector(skill_types: Set[str], type_chart: dict) -> Dict[str, float]:
    """计算打击面：对每种防御属性，能打出的最大克制倍率。"""
    coverage = {}
    for def_type in TYPES:
        max_mult = 0.0
        for atk_type in skill_types:
            mult = type_chart.get(atk_type, {}).get(def_type, 1.0)
            if mult > max_mult:
                max_mult = mult
        coverage[def_type] = max_mult
    return coverage


def calc_weakness_vector(primary: str, secondary: Optional[str], type_chart: dict) -> Dict[str, float]:
    """计算抗性面：被每种攻击属性攻击时的受伤倍率。"""
    weakness = {}
    for atk_type in TYPES:
        mult = type_chart.get(atk_type, {}).get(primary, 1.0)
        if secondary:
            mult *= type_chart.get(atk_type, {}).get(secondary, 1.0)
        weakness[atk_type] = mult
    return weakness


def classify_role(
    pet: dict,
    atk_skills: int,
    magic_skills: int,
    status_skills: int,
    tags: Set[str],
    has_weather: bool,
    has_priority: bool,
    has_heal: bool,
    has_dmg_reduction: bool,
) -> str:
    """分类精灵职责。"""
    stats = pet["stats"]
    hp = stats["hp"]
    atk = stats["atk"]
    sp_atk = stats["sp_atk"]
    defense = stats["defense"]
    sp_def = stats["sp_def"]
    speed = stats["speed"]

    total_damage = atk + sp_atk
    total_defense = defense + sp_def

    # 天气手
    if has_weather:
        return "天气手"

    # 坦克: 高耐久 + 减伤/回血，且不以输出为主
    if (has_dmg_reduction or has_heal) and total_defense > 180 and max(atk, sp_atk) < 110:
        return "坦克"

    # 辅助: 以变化技为主 + 有增益
    if status_skills >= atk_skills + magic_skills and (has_heal or has_dmg_reduction):
        return "辅助"

    # 控场: 大量异常状态
    status_tags = {"灼烧", "中毒", "冻结", "星陨", "萌化", "寄生"}
    if len(tags & status_tags) >= 2:
        return "控场"

    # 高速游击: 高速 + 先手
    if speed > 110 and has_priority:
        return "高速游击"

    # 输出分类
    if atk > sp_atk * 1.2 and atk_skills >= magic_skills:
        return "物理输出"
    if sp_atk > atk * 1.2 and magic_skills >= atk_skills:
        return "魔法输出"
    if atk_skills > 0 and magic_skills > 0:
        return "双刀"

    # 有攻有防 → 一般/平衡
    return "一般"


def select_optimal_skills(
    skill_names: List[str],
    parsed_skills_map: Dict[str, dict],
    pet_atk: int,
    pet_sp_atk: int,
) -> List[str]:
    """
    从精灵的全部技能中选择最优4技能。

    策略:
    1. 区分物理/魔法/变化
    2. 根据物攻/魔攻高低确定偏好方向
    3. 挑高威力 + 高覆盖技能
    4. 如果变化技特别好（天气/印记/减伤），也考虑
    """
    preferred = "physical" if pet_atk > pet_sp_atk else "magical"

    physical_skills: List[tuple] = []
    magic_skills: List[tuple] = []
    status_skills: List[tuple] = []

    for name in skill_names:
        ps = parsed_skills_map.get(name)
        if not ps:
            continue
        power = ps.get("power", 0)
        energy = ps.get("energy", 0)
        cat = ps.get("category", "")
        tags = ps.get("synergy_tags", [])
        is_counter = ps.get("counter_any", False)

        # 得分: 威力为主，tags为加成
        score = power * 1.0
        if is_counter:
            score += 10  # 应对技能有额外价值
        if "连击" in tags:
            score += 15
        if energy <= 2:
            score += 5   # 低能耗加成
        score += len(tags) * 3  # 标签丰富度

        entry = (name, score, power, energy, tags)

        if cat == "物理":
            physical_skills.append(entry)
        elif cat == "魔法":
            magic_skills.append(entry)
        else:
            status_skills.append(entry)

    # 排序: 得分高→低
    physical_skills.sort(key=lambda x: -x[1])
    magic_skills.sort(key=lambda x: -x[1])
    status_skills.sort(key=lambda x: -x[1])

    selected: List[str] = []

    if preferred == "physical":
        # 优先2个物理
        if physical_skills:
            selected.append(physical_skills[0][0])
        if len(physical_skills) > 1:
            selected.append(physical_skills[1][0])
        # 尝试不同属性的魔法技能
        used_types = set()
        for _, _, _, _, tags in physical_skills[:2]:
            pass  # We'll track types more carefully if needed
        # 1个变化技
        if status_skills and len(selected) < 4:
            selected.append(status_skills[0][0])
        # 补魔法或物理
        if len(selected) < 4 and magic_skills:
            selected.append(magic_skills[0][0])
        if len(selected) < 4 and len(physical_skills) > 2:
            selected.append(physical_skills[2][0])
    else:
        # 优先2个魔法
        if magic_skills:
            selected.append(magic_skills[0][0])
        if len(magic_skills) > 1:
            selected.append(magic_skills[1][0])
        # 1个变化技
        if status_skills and len(selected) < 4:
            selected.append(status_skills[0][0])
        # 补物理
        if len(selected) < 4 and physical_skills:
            selected.append(physical_skills[0][0])
        if len(selected) < 4 and len(magic_skills) > 2:
            selected.append(magic_skills[2][0])

    # 如果还不够4个，从任意池中补
    all_ranked = sorted(physical_skills + magic_skills + status_skills, key=lambda x: -x[1])
    for name, _, _, _, _ in all_ranked:
        if name not in selected:
            selected.append(name)
        if len(selected) >= 4:
            break

    return selected[:4]


# ── 主函数 ────────────────────────────────────────────────────────

def build_profiles() -> List[PetProfile]:
    """主入口：生成全部375只精灵的画像。"""
    base = Path(__file__).resolve().parents[3]

    # 加载数据
    pets = load_json(base / "scraper" / "output" / "pets.json")
    parsed_skills_list = load_json(base / "ml" / "data" / "parsed_skills.json")
    learnset_list = load_json(base / "scraper" / "output" / "learnset.json")
    type_chart = load_json(base / "scraper" / "output" / "type_chart.json")["chart"]

    # 建立查表索引
    parsed_skills_map: Dict[str, dict] = {s["name"]: s for s in parsed_skills_list}
    pet_learnset: Dict[int, List[str]] = {}
    for entry in learnset_list:
        pid = entry["pet_id"]
        if pid not in pet_learnset:
            pet_learnset[pid] = []
        pet_learnset[pid].append(entry["skill_name"])

    profiles: List[PetProfile] = []
    role_stats: Dict[str, int] = {}

    for pet in pets:
        pid = pet["id"]
        # 适配新旧数据格式：新数据种族值平铺，旧数据在 stats 子对象
        if "stats" not in pet:
            hp = int(pet.get("hp", 0) or 0)
            atk = int(pet.get("atk", 0) or 0)
            defense = int(pet.get("defense", 0) or 0)
            sp_atk = int(pet.get("sp_atk", 0) or 0)
            sp_def = int(pet.get("sp_def", 0) or 0)
            speed = int(pet.get("speed", 0) or 0)
            pet["stats"] = {
                "hp": hp, "atk": atk, "defense": defense,
                "sp_atk": sp_atk, "sp_def": sp_def, "speed": speed,
                "total": hp + atk + defense + sp_atk + sp_def + speed,
            }
        stats = pet["stats"]
        ability = pet.get("ability", "")

        # 获取全部技能（learnset 为主，pet 自带 skills 为辅）
        all_skill_names = list(pet_learnset.get(pid, []))
        for s in pet.get("skills", []):
            if s not in all_skill_names:
                all_skill_names.append(s)

        # 分类技能
        physical_count = 0
        magic_count = 0
        status_count = 0
        all_tags: Set[str] = set()
        skill_types: Set[str] = set()
        has_weather = False
        has_priority = False
        has_heal = False
        has_dmg_reduction = False
        total_energy = 0
        energy_count = 0

        for sname in all_skill_names:
            ps = parsed_skills_map.get(sname)
            if not ps:
                continue
            cat = ps.get("category", "")
            if cat == "物理":
                physical_count += 1
            elif cat == "魔法":
                magic_count += 1
            else:
                status_count += 1

            for t in ps.get("synergy_tags", []):
                all_tags.add(t)

            skill_types.add(ps.get("type", ""))

            if ps.get("applies_weather"):
                has_weather = True
            if ps.get("priority", 0) > 0:
                has_priority = True
            if ps.get("has_lifesteal", False) or ("回血" in (ps.get("effect_raw", "")) or "回复" in ps.get("effect_raw", "")):
                has_heal = True
            if ps.get("has_damage_reduction", False):
                has_dmg_reduction = True

            e = ps.get("energy", 0)
            if e > 0:
                total_energy += e
                energy_count += 1

        # 选取最优4技能
        optimal = select_optimal_skills(
            all_skill_names, parsed_skills_map, stats["atk"], stats["sp_atk"]
        )

        # 攻击倾向
        if stats["atk"] > stats["sp_atk"] * 1.15:
            pref = "physical"
        elif stats["sp_atk"] > stats["atk"] * 1.15:
            pref = "magical"
        else:
            pref = "mixed"

        # 有效种族值
        if pref == "physical":
            eff_atk = stats["atk"]
            eff_sp_atk = 0
        elif pref == "magical":
            eff_atk = 0
            eff_sp_atk = stats["sp_atk"]
        else:
            eff_atk = stats["atk"]
            eff_sp_atk = stats["sp_atk"]

        # 职责分类
        role = classify_role(pet, physical_count, magic_count, status_count,
                            all_tags, has_weather, has_priority, has_heal, has_dmg_reduction)
        role_stats[role] = role_stats.get(role, 0) + 1

        # 打击面/抗性面
        cov = calc_coverage_vector(skill_types, type_chart)
        weak = calc_weakness_vector(
            pet.get("type_primary", ""),
            pet.get("type_secondary"),
            type_chart
        )

        # 能量效率
        avg_energy = total_energy / energy_count if energy_count > 0 else 0
        has_energy_recovery = "能量操控" in all_tags

        profile = PetProfile(
            id=pid,
            name=pet["name"],
            type_primary=pet.get("type_primary", ""),
            type_secondary=pet.get("type_secondary"),
            stat_hp=stats["hp"],
            stat_atk=stats["atk"],
            stat_def=stats["defense"],
            stat_sp_atk=stats["sp_atk"],
            stat_sp_def=stats["sp_def"],
            stat_speed=stats["speed"],
            stat_total=stats["total"],
            effective_atk=eff_atk,
            effective_sp_atk=eff_sp_atk,
            effective_def=stats["defense"],
            effective_sp_def=stats["sp_def"],
            effective_speed=stats["speed"],
            effective_hp=stats["hp"],
            role=role,
            attack_preference=pref,
            optimal_skills=optimal,
            physical_skill_count=physical_count,
            magic_skill_count=magic_count,
            status_skill_count=status_count,
            coverage_vector=cov,
            weakness_vector=weak,
            avg_energy_cost=round(avg_energy, 1),
            has_energy_recovery=has_energy_recovery,
            synergy_tags=sorted(all_tags),
            ability=ability,
        )
        profiles.append(profile)

    # 输出
    output_path = base / "ml" / "data" / "pet_profiles.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results = [asdict(p) for p in profiles]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 统计
    print(f"精灵画像生成完成: {len(profiles)} 只")
    print(f"\n职责分布:")
    for role, count in sorted(role_stats.items(), key=lambda x: -x[1]):
        bar = "█" * min(count, 50)
        print(f"  {role:8s} {count:3d} {bar}")

    # 示例
    demo = [p for p in profiles if p.name == "迪莫"][0]
    print(f"\n示例: {demo.name}")
    print(f"  属性: {demo.type_primary} {demo.type_secondary or ''}")
    print(f"  职责: {demo.role}  倾向: {demo.attack_preference}")
    print(f"  最优4技能: {demo.optimal_skills}")
    print(f"  标签: {demo.synergy_tags}")
    print(f"  有效种族值: atk={demo.effective_atk} sp_atk={demo.effective_sp_atk}")
    print(f"  能量效率: {demo.avg_energy_cost} avg, 回能={demo.has_energy_recovery}")
    # combat scores
    high_cov = sorted(demo.coverage_vector.items(), key=lambda x: -x[1])[:3]
    high_weak = sorted(demo.weakness_vector.items(), key=lambda x: -x[1])[:3]
    print(f"  最佳打击: {high_cov}")
    print(f"  最大弱点: {high_weak}")

    print(f"\n输出: {output_path}")
    return profiles


if __name__ == "__main__":
    build_profiles()

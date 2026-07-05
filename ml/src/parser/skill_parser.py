"""
技能解析器 — 对 494 个技能做完整结构化标注

输入: scraper/output/skills.json
输出: ml/data/parsed_skills.json

每技能标注:
  - 攻击类型（物攻/魔攻/非攻击）
  - 有效种族值关联
  - 应对机制（攻击/防御/状态）
  - 先手值 / 传动值 / 连击数 / 蓄力 / 脱离
  - 施加的状态/印记/天气
  - 联动标签（synergy_tags）
"""

import re
import json
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field, asdict

from synergy_tagger import (
    tag_skill,
    extract_counter_info,
    extract_priority,
    extract_transmission,
    extract_hits,
    detect_charge,
    detect_retreat,
)


# ── 数据模型 ──────────────────────────────────────────────────────

@dataclass
class ParsedSkill:
    name: str
    type: str                          # 属性（火/水/草...）
    category: str                      # 物理/魔法/变化
    power: int
    energy: int
    accuracy: int

    # 攻击类型
    is_attack: bool                    # 是否为攻击技（威力>0 且非变化）
    attack_type: Optional[str]         # "physical" / "magical" / None
    effective_stat: Optional[str]      # "atk" / "sp_atk" / None

    # 机制标注
    counter_attack: bool               # 应对攻击
    counter_defense: bool              # 应对防御
    counter_status: bool               # 应对状态
    counter_any: bool                  # 任意应对类型

    priority: int                      # 先手值（0=正常，+1=先手，-1=后手）
    has_charge: bool                   # 蓄力
    has_retreat: bool                  # 脱离
    transmission: int                  # 传动值（0=无传动）

    hits: int                          # 连击数（0=单次/无连击）

    # 施加的效果
    applies_status: List[str]          # 施加的异常状态
    applies_weather: Optional[str]     # 改变的天气类型
    applies_mark: List[str]            # 施加的印记

    # 其他标签
    has_lifesteal: bool                # 吸血
    has_damage_reduction: bool         # 减伤
    has_team_effect: bool              # 队友联动效果
    synergy_tags: List[str]            # 全部联动标签

    effect_raw: str                    # 原始效果文本


# ── 效果提取 ──────────────────────────────────────────────────────

def extract_applied_statuses(effect: str) -> List[str]:
    """从效果文本提取施加的异常状态。"""
    statuses = []
    patterns = {
        "灼烧": r"(?:敌方|目标|对手).*?灼烧|灼烧.*?(?:敌方|目标|对手)",
        "中毒": r"(?:敌方|目标|对手).*?中毒|中毒.*?(?:敌方|目标|对手)",
        "冻结": r"(?:敌方|目标|对手).*?冻结|冻结.*?(?:敌方|目标|对手)",
        "星陨": r"(?:敌方|目标|对手).*?星陨|星陨.*?(?:敌方|目标|对手)",
        "萌化": r"萌化转移|使.*萌化|萌化.*敌方",
        "寄生": r"寄生",
    }
    for status, pattern in patterns.items():
        if re.search(pattern, effect):
            statuses.append(status)
    return statuses


def extract_weather(effect: str) -> Optional[str]:
    """提取改变的天气类型。"""
    weathers = ["暴风雪", "沙暴", "雨天"]
    for w in weathers:
        if w in effect and ("将天气改为" in effect or "天气为" in effect):
            return w
    return None


def extract_marks(effect: str) -> List[str]:
    """提取施加的印记类型。"""
    marks = []
    mark_names = [
        "湿润印记", "龙噬印记", "蓄势印记", "风起印记",
        "蓄电印记", "光合印记", "攻击印记", "萌芽印记",
        "减速印记", "降灵印记", "星陨印记", "中毒印记",
        "棘刺印记", "迟缓印记", "印记",
    ]
    for m in mark_names:
        if m in effect:
            marks.append(m)
    return marks


def extract_team_effect(effect: str) -> bool:
    """检测是否有队友联动效果。"""
    patterns = [r"奉献", r"场下", r"队友", r"借用", r"继承.*增益"]
    return any(re.search(p, effect) for p in patterns)


# ── 主解析函数 ────────────────────────────────────────────────────

def parse_skill(raw: dict) -> ParsedSkill:
    """解析单个原始技能为结构化 ParsedSkill。"""
    name = raw.get("name", "")
    typ = raw.get("type", "")
    cat = raw.get("category", "")
    power = raw.get("power", 0)
    energy = raw.get("energy", 0)
    accuracy = raw.get("accuracy", 100)
    effect = raw.get("effect", "")

    # 攻击类型
    is_attack = cat in ("物理", "魔法") and power > 0
    if cat == "物理":
        attack_type = "physical"
        effective_stat = "atk"
    elif cat == "魔法":
        attack_type = "magical"
        effective_stat = "sp_atk"
    else:
        attack_type = None
        effective_stat = None

    # 应对机制
    counter = extract_counter_info(effect)

    # 机制标签
    pri = extract_priority(effect)
    trans = extract_transmission(effect)
    hits = extract_hits(effect)
    charge = detect_charge(effect)
    retreat = detect_retreat(effect)

    # 效果提取
    statuses = extract_applied_statuses(effect)
    weather = extract_weather(effect)
    marks = extract_marks(effect)

    # 特殊标签
    lifesteal = bool(re.search(r"吸血", effect))
    dmg_reduction = bool(re.search(r"减伤", effect))
    team = extract_team_effect(effect)

    # 联动标签
    tags = tag_skill(effect, name, cat)

    return ParsedSkill(
        name=name,
        type=typ,
        category=cat,
        power=power,
        energy=energy,
        accuracy=accuracy,
        is_attack=is_attack,
        attack_type=attack_type,
        effective_stat=effective_stat,
        counter_attack=counter["has_counter_attack"],
        counter_defense=counter["has_counter_defense"],
        counter_status=counter["has_counter_status"],
        counter_any=any(counter.values()),
        priority=pri,
        has_charge=charge,
        has_retreat=retreat,
        transmission=trans,
        hits=hits,
        applies_status=statuses,
        applies_weather=weather,
        applies_mark=marks,
        has_lifesteal=lifesteal,
        has_damage_reduction=dmg_reduction,
        has_team_effect=team,
        synergy_tags=tags,
        effect_raw=effect,
    )


def parse_all(raw_skills: List[dict]) -> List[ParsedSkill]:
    """解析全部技能。"""
    return [parse_skill(s) for s in raw_skills]


def to_dict(parsed: ParsedSkill) -> dict:
    """将 ParsedSkill 转为可序列化的字典。"""
    d = asdict(parsed)
    # 清理空值
    if not d["applies_weather"]:
        d["applies_weather"] = None
    if not d["attack_type"]:
        d["attack_type"] = None
    if not d["effective_stat"]:
        d["effective_stat"] = None
    # 移除 redundant 字段，synergy_tags 已包含完整信息
    return d


# ── 主入口 ────────────────────────────────────────────────────────

def main():
    base = Path(__file__).resolve().parents[3]  # 洛克王国/ 目录
    input_path = base / "scraper" / "output" / "skills.json"
    output_path = base / "ml" / "data" / "parsed_skills.json"

    with open(input_path, "r", encoding="utf-8") as f:
        raw_skills = json.load(f)

    parsed = parse_all(raw_skills)
    results = [to_dict(p) for p in parsed]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 统计
    attacks = sum(1 for p in parsed if p.is_attack)
    status_skills = sum(1 for p in parsed if p.category == "变化")
    counters = sum(1 for p in parsed if p.counter_any)
    priority_skills = sum(1 for p in parsed if p.priority != 0)
    weather_skills = sum(1 for p in parsed if p.applies_weather)
    mark_skills = sum(1 for p in parsed if p.applies_mark)
    tagged = sum(1 for p in parsed if p.synergy_tags)

    print(f"解析完成: {len(results)} 个技能")
    print(f"  攻击技: {attacks} (物理{sum(1 for p in parsed if p.attack_type=='physical')}, 魔法{sum(1 for p in parsed if p.attack_type=='magical')})")
    print(f"  变化技: {status_skills}")
    print(f"  有应对: {counters}")
    print(f"  有先手: {priority_skills}")
    print(f"  有天气: {weather_skills}")
    print(f"  有印记: {mark_skills}")
    print(f"  有标签: {tagged}")
    print(f"\n输出: {output_path}")

    # 展示一个完整示例
    print(f"\n示例 (灼烧相关技能):")
    for p in parsed:
        if "灼烧" in p.synergy_tags:
            print(f"  {p.name} [{p.type}/{p.category}] 威力{p.power} 能耗{p.energy}")
            print(f"    状态: {p.applies_status}  天气: {p.applies_weather}  印记: {p.applies_mark}")
            print(f"    标签: {p.synergy_tags}")
            print(f"    效果: {p.effect_raw[:80]}...")
            break


if __name__ == "__main__":
    main()

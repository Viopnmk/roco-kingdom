"""
精灵特性文本标注器 — 从特性描述中提取机械标签

标签体系（基于 mechanics.md 和实际数据分析）：
  数值增减: 增伤 / 减伤 / 回血 / 回能 / 降耗 / 提速
  机制联动: 应对增强 / 状态联动 / 印记联动 / 天气联动
  时机效果: 入场效果 / 退场效果 / 回合结束
  特殊机制: 迸发 / 蓄力联动 / 传动联动 / 能量操控
"""

import re
from typing import List, Dict, Tuple


# ── 特性标签定义 ──────────────────────────────────────────────────

ABILITY_TAG_DEFS: Dict[str, Tuple[str, str]] = {
    # ── 数值增减 ──
    "增伤": (
        r"攻击\+|伤害\+|双攻\+|物攻\+|魔攻\+|威力\+|攻击伤害\+",
        "提升攻击/伤害百分比",
    ),
    "减伤": (
        r"减伤|受到伤害-|受到.*伤害降低|受到.*攻击伤害减半|受到.*攻击伤害-",
        "减少受到伤害",
    ),
    "回血": (
        r"回复\d+%生命|回复\d+点生命|吸血|回复.*血量|回复.*自身.*血量|回血|回复生命",
        "恢复HP",
    ),
    "回能": (
        r"回复\d+点能量|回复\d+能量|能量\+|回复能量",
        "恢复能量",
    ),
    "降耗": (
        r"能耗-\d+|能量消耗-\d+|能耗减少|能耗-|能量消耗降低",
        "降低技能能耗",
    ),
    "提速": (
        r"速度\+|提高速度|速度提升",
        "提升速度",
    ),

    # ── 机制联动 ──
    "应对增强": (
        r"应对成功|应对后|每.*应对.*次|每成功应对",
        "应对相关效果",
    ),
    "状态联动": (
        r"灼烧|中毒|冻结|星陨|萌化|寄生|每层|每\d+层|每有",
        "与异常状态层数联动的效果",
    ),
    "印记联动": (
        r"印记.*不.*替换|印记.*共存|印记.*同时|偷取.*印记|印记",
        "印记相关特性",
    ),
    "天气联动": (
        r"天气|暴风雪|沙暴|雨天",
        "天气相关特性",
    ),
    "蓄力联动": (
        r"蓄力|迸发",
        "蓄力/迸发相关特性",
    ),
    "传动联动": (
        r"传动|位置|位移动|换位",
        "传动/位置相关特性",
    ),
    "脱离联动": (
        r"脱离|替换|下场|退场|离开",
        "退场/替换相关特性",
    ),

    # ── 时机效果 ──
    "入场效果": (
        r"入场时|进场时|替换上场时",
        "入场触发效果",
    ),
    "退场效果": (
        r"退场时|离场时|死亡时|被击败时",
        "退场触发效果",
    ),
    "回合结束": (
        r"回合结束|回合末|回合.*时|回合开始|每回合|回合.*结束",
        "回合结束触发效果",
    ),

    # ── 特殊机制 ──
    "能量操控": (
        r"能量|能耗|失去.*能量|偷取.*能量|获得.*能量|能量操控",
        "能量相关特性",
    ),
    "属性切换": (
        r"属性.*变|血脉|学习.*技能|血脉技能|属性变为",
        "属性改变/血脉相关",
    ),
    "复活": (
        r"复活|重生",
        "死亡后复活",
    ),
}


def tag_ability(ability_text: str) -> List[str]:
    """
    从特性文本中提取机械标签。

    Args:
        ability_text: 特性描述文本

    Returns:
        标签列表，按发现顺序排列
    """
    tags: List[str] = []
    if not ability_text:
        return tags

    for tag_name, (pattern, _desc) in ABILITY_TAG_DEFS.items():
        if re.search(pattern, ability_text):
            tags.append(tag_name)

    return tags


def extract_ability_value(ability_text: str, pattern: str) -> float:
    """
    从特性文本中提取数值（百分比或整数）。

    Args:
        ability_text: 特性文本
        pattern: 正则模式（必须包含一个捕获组）

    Returns:
        提取的数值，默认0
    """
    m = re.search(pattern, ability_text)
    if not m:
        return 0.0
    try:
        return float(m.group(1))
    except (ValueError, IndexError):
        return 0.0


def tag_all_pets(pets: List[dict]) -> List[dict]:
    """
    批量标注精灵特性。

    Args:
        pets: 精灵列表（来自 scraper/output/pets.json）

    Returns:
        带 ability_tags 字段的精灵列表
    """
    results = []
    stats: Dict[str, int] = {}

    for pet in pets:
        ability = pet.get("ability", "")
        tags = tag_ability(ability)

        for t in tags:
            stats[t] = stats.get(t, 0) + 1

        pet_copy = dict(pet)
        pet_copy["ability_tags"] = tags
        results.append(pet_copy)

    print(f"特性标注完成: {len(results)} 只精灵")
    print(f"标签分布:")
    for tag, count in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"  {tag:8s} {count:3d}")

    untagged = [p["name"] for p in results if not p["ability_tags"]]
    if untagged:
        print(f"\n无标签精灵 ({len(untagged)} 只): {untagged[:10]}...")

    return results


if __name__ == "__main__":
    import json
    from pathlib import Path

    base = Path(__file__).resolve().parents[3]
    data_path = base / "scraper" / "output" / "pets.json"
    with open(data_path, "r", encoding="utf-8") as f:
        pets = json.load(f)

    results = tag_all_pets(pets)

    # 展示几个样例
    print("\n样例:")
    for r in results[:5]:
        name = r["name"]
        ability = r.get("ability", "")[:60]
        tags = r.get("ability_tags", [])
        print(f"  {name}: {ability}... → {tags}")

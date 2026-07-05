"""
技能联动标签标注器 — 基于正则+关键词从技能效果文本中提取标签

标签体系（基于 mechanics.md 确认的游戏机制）：
  异常状态: 灼烧 / 中毒 / 冻结 / 星陨 / 萌化 / 寄生
  技能类型: 应对攻击 / 应对防御 / 应对状态 / 先手 / 蓄力 / 传动 / 脱离
  特效标签: 连击 / 吸血 / 减伤 / 天气 / 印记 / 迅捷 / 折返 / 迸发 / 巧变
  战术风格: 能量操控 / 增益传递 / 打断
"""

import re
from typing import Tuple, Dict, List


# ── 标签定义 ──────────────────────────────────────────────────────

# 每个标签: (正则模式, 说明)
TAG_DEFS: Dict[str, Tuple[str, str]] = {
    # ── 异常状态（核心联动维度） ──
    "灼烧": (
        r"灼烧|灼伤|充分燃烧",
        "施加/引爆/联动灼烧层数",
    ),
    "中毒": (
        r"(?:每有\d+层)?中毒(?!印记)|剧毒|以毒攻毒|毒伤",
        "施加/引爆/联动中毒层数",
    ),
    "冻结": (
        r"冻结|冰冻",
        "施加/引爆冻结层数",
    ),
    "星陨": (
        r"星陨",
        "施加/引爆星陨层数",
    ),
    "萌化": (
        r"萌化",
        "萌化相关效果",
    ),
    "寄生": (
        r"寄生",
        "寄生效果",
    ),

    # ── 技能类型标签 ──
    "应对攻击": (
        r"应对攻击",
        "被攻击时触发应对效果",
    ),
    "应对防御": (
        r"应对防御",
        "防御时触发应对效果",
    ),
    "应对状态": (
        r"应对状态",
        "对手使用状态技能时触发应对效果",
    ),
    "先手": (
        r"先手\+?\d*",
        "先手出招（优先行动）",
    ),
    "蓄力": (
        r"蓄力",
        "本回合蓄力，下回合释放",
    ),
    "传动": (
        r"传动\d*",
        "技能在1-4号位间每回合移动",
    ),
    "脱离": (
        r"脱离|替换",
        "主动下场换宠",
    ),

    # ── 特效标签 ──
    "连击": (
        r"\d+\s*连击|连击数",
        "以相同威力造成多次伤害",
    ),
    "吸血": (
        r"吸血|吸取.*生命|回复.*造成伤害",
        "造成伤害的一部分回复自身HP",
    ),
    "减伤": (
        r"减伤\d*%?",
        "受到伤害减少",
    ),
    "天气": (
        r"将天气改为|天气为|暴风雪|沙暴|雨天|天气",
        "改变/影响天气",
    ),
    "印记": (
        r"[^的]印记|印记，",
        "施加/操作印记",
    ),
    "迅捷": (
        r"迅捷",
        "入场立刻释放技能",
    ),
    "折返": (
        r"折返",
        "离开战场换精灵",
    ),
    "迸发": (
        r"迸发",
        "迸发触发（条件待确认）",
    ),
    "巧变": (
        r"巧变",
        "技能类型转换",
    ),

    # ── 战术风格标签 ──
    "能量操控": (
        r"回[复]?能|能量\+|偷[取走].*能量|失去.*能量|能耗[+\\-]|消耗.*能量",
        "影响能量收入/支出",
    ),
    "增益传递": (
        r"继承.*增益|奉献|传递",
        "将增益效果传递给队友",
    ),
    "打断": (
        r"打断",
        "打断对手技能",
    ),
}


def tag_skill(effect_text: str, skill_name: str = "", skill_category: str = "") -> List[str]:
    """
    从技能效果文本中提取联动标签。

    Args:
        effect_text: 技能效果原始文本
        skill_name: 技能名称（用于辅助判断）
        skill_category: 物理/魔法/变化

    Returns:
        标签列表，按发现顺序排列
    """
    tags: List[str] = []
    if not effect_text:
        return tags

    for tag_name, (pattern, _desc) in TAG_DEFS.items():
        if re.search(pattern, effect_text):
            tags.append(tag_name)

    # 去重保持顺序
    seen: set = set()
    result = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            result.append(t)

    return result


def tag_batch(skills: List[dict]) -> List[dict]:
    """
    批量标注技能，返回带标签的技能列表。

    Args:
        skills: 技能字典列表（来自 scraper/output/skills.json）

    Returns:
        带 tags 字段的技能列表
    """
    results = []
    stats: Dict[str, int] = {}
    for skill in skills:
        effect = skill.get("effect", "")
        category = skill.get("category", "")
        name = skill.get("name", "")
        tags = tag_skill(effect, name, category)

        for t in tags:
            stats[t] = stats.get(t, 0) + 1

        results.append({
            "name": name,
            "type": skill.get("type", ""),
            "category": category,
            "power": skill.get("power", 0),
            "energy": skill.get("energy", 0),
            "accuracy": skill.get("accuracy", 100),
            "effect": effect,
            "tags": tags,
        })

    # 统计信息
    print(f"标注完成: {len(results)} 个技能")
    print(f"标签分布:")
    for tag, count in sorted(stats.items(), key=lambda x: -x[1]):
        bar = "█" * min(count, 40)
        print(f"  {tag:8s} {count:3d} {bar}")

    # 检查无标签技能
    untagged = [s["name"] for s in results if not s["tags"]]
    if untagged:
        print(f"\n无标签技能 ({len(untagged)} 个):")
        for name in sorted(untagged):
            print(f"  - {name}")

    return results


# ── 附加分析 ──────────────────────────────────────────────────────

def extract_counter_info(effect_text: str) -> Dict[str, bool]:
    """提取应对机制信息。"""
    return {
        "has_counter_attack": bool(re.search(r"应对攻击", effect_text)),
        "has_counter_defense": bool(re.search(r"应对防御", effect_text)),
        "has_counter_status": bool(re.search(r"应对状态", effect_text)),
    }


def extract_priority(effect_text: str) -> int:
    """提取先手值。"""
    m = re.search(r"先手\+?(\d*)", effect_text)
    if not m:
        return 0
    val = m.group(1)
    return int(val) if val else 1


def extract_transmission(effect_text: str) -> int:
    """提取传动值。"""
    m = re.search(r"传动(\d+)", effect_text)
    return int(m.group(1)) if m else 0


def extract_hits(effect_text: str) -> int:
    """提取连击数。"""
    m = re.search(r"(\d+)\s*连击", effect_text)
    return int(m.group(1)) if m else 0


def detect_charge(effect_text: str) -> bool:
    """检测蓄力。"""
    return bool(re.search(r"蓄力", effect_text))


def detect_retreat(effect_text: str) -> bool:
    """检测脱离。"""
    return bool(re.search(r"脱离|替换", effect_text))


if __name__ == "__main__":
    import json
    import os
    from pathlib import Path

    base = Path(__file__).resolve().parents[3]  # ml/ 目录
    data_path = base / "scraper" / "output" / "skills.json"
    with open(data_path, "r", encoding="utf-8") as f:
        skills = json.load(f)

    results = tag_batch(skills)

    out_path = base / "ml" / "data" / "parsed_skills.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n输出: {out_path}")

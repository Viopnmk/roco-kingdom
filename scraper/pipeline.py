"""
数据清洗管道 —— 将爬取的原始数据转换为前端可用的标准格式
"""

import json
import re
from pathlib import Path

from config import OUTPUT_DIR, TYPES


def clean_pets(raw_pets: list[dict]) -> list[dict]:
    """清洗精灵数据，标准化字段格式。"""
    cleaned = []
    for raw in raw_pets:
        if not raw.get("name"):
            continue

        pet = {
            "id": _clean_int(raw.get("number", "")),
            "name": raw["name"].strip(),
            "type_primary": _clean_type(raw.get("type_primary", "")),
            "type_secondary": _clean_type(raw.get("type_secondary", "")),
            "stats": {
                "hp": _clean_int(raw.get("hp", 0)),
                "atk": _clean_int(raw.get("atk", 0)),
                "defense": _clean_int(raw.get("defense", 0)),
                "sp_atk": _clean_int(raw.get("sp_atk", 0)),
                "sp_def": _clean_int(raw.get("sp_def", 0)),
                "speed": _clean_int(raw.get("speed", 0)),
                "total": 0,
            },
            "ability": _clean_str(raw.get("ability", "")),
            "height": _clean_str(raw.get("height", "")),
            "weight": _clean_str(raw.get("weight", "")),
            "description": _clean_str(raw.get("description", "")),
            "evolution_chain": _clean_evolution(raw.get("evolution", "")),
            "how_to_get": _clean_str(raw.get("how_to_get", "")),
            "skills": _clean_list(raw.get("skills", [])),
            "stone_skills": _clean_list(raw.get("stone_skills", [])),
            "bloodline_skills": _clean_list(raw.get("bloodline_skills", [])),
            "source": raw.get("source", "bwiki"),
        }

        # 计算种族值总和
        stats = pet["stats"]
        vals = [stats["hp"], stats["atk"], stats["defense"],
                stats["sp_atk"], stats["sp_def"], stats["speed"]]
        if all(v > 0 for v in vals):
            stats["total"] = sum(vals)
        else:
            stats["total"] = raw.get("total", sum(vals))

        # 过滤种族值全空的精灵
        if stats["total"] == 0:
            continue

        # 二次属性为空时去掉
        if not pet["type_secondary"]:
            del pet["type_secondary"]

        cleaned.append(pet)

    # 按编号排序
    cleaned.sort(key=lambda p: p["id"] if p["id"] else 9999)
    return cleaned


def clean_skills(raw_skills: dict) -> list[dict]:
    """清洗技能数据。"""
    cleaned = []
    for name, raw in raw_skills.items():
        skill = {
            "name": name.strip(),
            "type": _clean_type(raw.get("attribute", raw.get("type", ""))),
            "category": _clean_category(raw.get("category", "")),
            "power": _clean_int(raw.get("power", 0)),
            "pp": _clean_int(raw.get("pp", 0)),
            "accuracy": _clean_int(raw.get("accuracy", 100)),
            "energy": _clean_int(raw.get("energy_consumption", raw.get("energy", 0))),
            "effect": _clean_str(raw.get("description", raw.get("effect", ""))),
        }
        cleaned.append(skill)

    cleaned.sort(key=lambda s: s["name"])
    return cleaned


def build_skill_learnset(pets: list[dict], skills: list[dict]) -> list[dict]:
    """构建精灵-技能学习面关联表，包含来源分类。"""
    learnset = []
    skill_names = {s["name"] for s in skills}

    categories = [
        ("skills", "level"),
        ("stone_skills", "stone"),
        ("bloodline_skills", "bloodline"),
    ]

    for pet in pets:
        for field, source in categories:
            for skill_name in pet.get(field, []):
                if skill_name in skill_names:
                    learnset.append({
                        "pet_id": pet["id"],
                        "pet_name": pet["name"],
                        "skill_name": skill_name,
                        "source": source,
                    })

    return learnset


def _clean_int(val) -> int:
    """提取整数值。"""
    if isinstance(val, int):
        return val
    if isinstance(val, str):
        nums = re.findall(r"\d+", val)
        return int(nums[0]) if nums else 0
    return 0


def _clean_str(val) -> str:
    """清理字符串。"""
    if not val:
        return ""
    return str(val).strip()


def _clean_list(val) -> list:
    """确保返回列表。"""
    if isinstance(val, list):
        return [str(v).strip() for v in val if v]
    if isinstance(val, str):
        # 按常见分隔符拆分
        items = re.split(r"[,，、/]", val)
        return [i.strip() for i in items if i.strip()]
    return []


def _clean_type(val: str) -> str:
    """标准化属性名称。"""
    val = _clean_str(val)
    if not val:
        return ""
    if val in TYPES:
        return val
    # 模糊匹配
    for t in TYPES:
        if t in val or val in t:
            return t
    return val


def _clean_category(val: str) -> str:
    """标准化技能类型（物攻/魔攻/变化）。"""
    val = _clean_str(val)
    cats = {"物攻": "物理", "魔攻": "魔法", "变化": "变化",
            "物理": "物理", "魔法": "魔法", "特殊": "魔法",
            "状态": "变化", "防御": "变化", "辅助": "变化"}
    for k, v in cats.items():
        if k in val:
            return v
    return val


def _clean_evolution(val: str) -> list[dict]:
    """解析进化链。"""
    if not val:
        return []
    chain = []
    # 常见格式: 喵喵→喵呜→魔力猫 或 喵喵(16级)→喵呜(36级)→魔力猫
    stages = re.split(r"[→>]", val)
    for stage in stages:
        stage = stage.strip()
        name_match = re.search(r"([一-鿿]{2,6})", stage)
        level_match = re.search(r"(\d+)\s*级", stage)
        if name_match:
            chain.append({
                "name": name_match.group(1),
                "level": int(level_match.group(1)) if level_match else None,
            })
    return chain


def run_pipeline():
    """执行完整的数据清洗管道。"""
    print("=" * 50)
    print("数据清洗管道")
    print("=" * 50)

    raw_dir = Path("data")
    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. 加载原始数据
    print("\n[1/4] 加载原始数据...")
    pets_raw = _load_json(raw_dir / "pets_raw.json")
    skills_raw = _load_json(raw_dir / "skills_raw.json")
    external_raw = _load_json(raw_dir / "external_raw.json")
    lcx_pets = _load_json(raw_dir / "lcx_pets.json")
    lcx_skills = _load_json(raw_dir / "lcx_skills.json")
    print(f"  BWIKI精灵: {len(pets_raw)} 条")
    print(f"  技能: {len(skills_raw)} 条")
    print(f"  外部数据: {len(external_raw)} 条")
    print(f"  LCX精灵: {len(lcx_pets)} 条")
    print(f"  LCX技能: {len(lcx_skills)} 条")

    # 1.5 如果有 LCX 数据，优先使用
    if lcx_pets:
        pets_raw = lcx_pets
    if lcx_skills:
        skills_raw = {s["name"]: s for s in lcx_skills} if isinstance(lcx_skills, list) else lcx_skills

    # 2. 合并外部数据
    if external_raw:
        print("\n[2/4] 合并外部数据...")
        from spiders.biubiu import cross_validate
        pets_raw = cross_validate(pets_raw, external_raw)
        print(f"  合并后: {len(pets_raw)} 条")

    # 3. 清洗数据
    print("\n[3/4] 清洗数据...")
    pets = clean_pets(pets_raw)
    skills = clean_skills(skills_raw)
    learnset = build_skill_learnset(pets, skills)
    print(f"  精灵: {len(pets)} 只")
    print(f"  技能: {len(skills)} 个")
    print(f"  学习面: {len(learnset)} 条关联")

    # 4. 输出
    print("\n[4/4] 输出清洗后数据...")
    _save_json(output_dir / "pets.json", pets)
    _save_json(output_dir / "skills.json", skills)
    _save_json(output_dir / "learnset.json", learnset)

    # 输出类型克制数据
    from spiders.type_chart import get_all_type_data
    _save_json(output_dir / "type_chart.json", get_all_type_data())

    # 生成数据统计
    stats = {
        "total_pets": len(pets),
        "total_skills": len(skills),
        "total_learnset": len(learnset),
        "types": _type_stats(pets),
    }
    _save_json(output_dir / "stats.json", stats)
    print(f"\n  stats.json: {json.dumps(stats, ensure_ascii=False)}")

    print("\n管道完成!")


def _load_json(path: Path) -> list | dict:
    """安全加载JSON文件。"""
    if not path.exists():
        return [] if path.name.endswith("s_raw") else {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data):
    """保存JSON文件。"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _type_stats(pets: list[dict]) -> dict:
    """统计各属性精灵数量。"""
    type_count = {}
    for pet in pets:
        for t in [pet.get("type_primary"), pet.get("type_secondary")]:
            if t:
                type_count[t] = type_count.get(t, 0) + 1
    return type_count


if __name__ == "__main__":
    run_pipeline()

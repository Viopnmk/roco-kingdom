"""
wiki.lcx.cab 洛克王国资料库 —— API 爬虫
数据源: https://wiki.lcx.cab/lk/tujian.php
"""
import json
import time
from pathlib import Path

import requests

from config import RAW_DIR, REQUEST_DELAY, BATCH_SIZE

BASE = "https://wiki.lcx.cab/lk"
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": f"{BASE}/tujian.php",
})


def _api(endpoint: str, params: dict | None = None) -> dict | list:
    resp = session.get(f"{BASE}/{endpoint}", params=params, timeout=30)
    resp.raise_for_status()
    if resp.status_code == 403:
        raise RuntimeError(f"API 403: {resp.text[:200]}")
    return resp.json()


def scrape_pets() -> list[dict]:
    """从 LCX API 抓取所有宠物数据（含技能详情）。"""
    print("=" * 50)
    print("LCX 精灵图鉴爬虫")
    print("=" * 50)

    # 1. 获取技能列表（用于映射技能属性）
    print("\n[1/3] 获取技能列表...")
    all_skills = _api("get_all_skills.php")
    skill_map = {}
    for s in all_skills:
        skill_map[s["name"]] = {
            "type": s.get("attribute", ""),
            "category": s.get("category", ""),
            "power": s.get("power", ""),
            "pp": "",  # API 不含 PP
            "energy": s.get("energy_consumption", ""),
            "effect": s.get("description", ""),
        }
    print(f"  获取 {len(skill_map)} 个技能")

    # 2. 逐页获取宠物列表
    print("\n[2/3] 批量抓取宠物数据...")
    all_pets = []
    page = 1

    while True:
        data = _api("get_pokemon_data.php", {"page": page})
        if not data:
            break

        for raw in data:
            pet = _extract_pet(raw)
            if pet:
                # 关联技能详情
                enriched_skills = []
                for sname in pet.get("skills", []):
                    if sname in skill_map:
                        enriched_skills.append(skill_map[sname])
                all_pets.append(pet)

        print(f"  第 {page} 页: {len(data)} 只 (累计 {len(all_pets)})")
        page += 1
        time.sleep(REQUEST_DELAY)

    # 3. 保存
    print(f"\n[3/3] 保存数据...")
    Path(RAW_DIR).mkdir(parents=True, exist_ok=True)
    with open(Path(RAW_DIR) / "lcx_pets.json", "w", encoding="utf-8") as f:
        json.dump(all_pets, f, ensure_ascii=False, indent=2)
    with open(Path(RAW_DIR) / "lcx_skills.json", "w", encoding="utf-8") as f:
        json.dump(all_skills, f, ensure_ascii=False, indent=2)

    print(f"\n完成! 共抓取 {len(all_pets)} 只精灵")
    return all_pets


def _extract_pet(raw: dict) -> dict | None:
    """将 LCX API 返回的宠物数据转为标准格式。"""
    name = (raw.get("name") or "").strip()
    if not name:
        return None

    # 解析属性（可能是 "光, 地" 或 "毒, 草" 双属性格式）
    attrs = (raw.get("attributes") or "").strip()
    types = [t.strip() for t in attrs.replace("/", ",").split(",") if t.strip()]

    # 分别保留三类技能
    skills = [s.strip() for s in (raw.get("moves") or "").split(",") if s.strip()]
    stone_skills = [s.strip() for s in (raw.get("jinengshi") or "").split(",") if s.strip()]
    bloodline_skills = [s.strip() for s in (raw.get("xuemai") or "").split(",") if s.strip()]

    return {
        "name": name,
        "number": raw.get("t_id", raw.get("id", "")),
        "type_primary": types[0] if types else "",
        "type_secondary": types[1] if len(types) > 1 else "",
        "hp": raw.get("hp", ""),
        "atk": raw.get("attack", ""),
        "defense": raw.get("defense", ""),
        "sp_atk": raw.get("special_attack", ""),
        "sp_def": raw.get("special_defense", ""),
        "speed": raw.get("speed", ""),
        "ability": raw.get("abilities_text", ""),
        "height": raw.get("height", ""),
        "weight": raw.get("weight", ""),
        "description": raw.get("description", ""),
        "evolution": raw.get("evolution_condition", ""),
        "how_to_get": raw.get("tujian", ""),
        "skills": skills,
        "stone_skills": stone_skills,
        "bloodline_skills": bloodline_skills,
        "egg_group": raw.get("egg_group", ""),
        "source": "lcx",
    }

"""
交叉验证爬虫 —— 从 biubiu001 等攻略站抓取数据
用于和 BWIKI 数据互相印证，填补缺失字段
"""

import re
import json
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from config import RAW_DIR, REQUEST_DELAY

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    )
})


def fetch_html(url: str) -> BeautifulSoup | None:
    """获取页面 HTML 并返回 BeautifulSoup 对象。"""
    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "lxml")
    except requests.RequestException as e:
        print(f"  [WARN] 请求失败: {url} ({e})")
        return None


def scrape_biubiu_article(url: str) -> list[dict]:
    """从 biubiu001 文章页抓取精灵数据列表。
    页面结构需在运行时确认，这里做通用尝试。
    """
    soup = fetch_html(url)
    if not soup:
        return []

    pets = []

    # 尝试多种常见页面结构
    # 方式1: 表格 <table> 行
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 3:
            continue
        for row in rows[1:]:  # 跳过表头
            cells = row.find_all(["td", "th"])
            if len(cells) < 4:
                continue
            text_cells = [c.get_text(strip=True) for c in cells]
            pet = parse_table_row(text_cells)
            if pet:
                pets.append(pet)

    # 方式2: 段落文本中的列表（如 "1. xxx" 或 "● xxx"）
    if not pets:
        for p in soup.find_all(["p", "div"]):
            text = p.get_text(strip=True)
            # 尝试从大段文字中提取精灵名和数值
            extracted = extract_pets_from_text(text)
            if extracted:
                pets.extend(extracted)

    # 方式3: 结构化卡片/列表
    if not pets:
        cards = soup.find_all(["li", "section", "article"])
        for card in cards:
            text = card.get_text(strip=True)
            if len(text) > 20 and len(text) < 500:
                pet = extract_pet_from_block(text)
                if pet:
                    pets.append(pet)

    return pets


def parse_table_row(cells: list[str]) -> dict | None:
    """从表格行提取精灵数据。"""
    if not cells:
        return None

    # 尝试匹配：名称 | 属性 | 种族值 | 特性
    pet = {"name": cells[0]}

    # 识别数字（种族值）
    nums = re.findall(r"\d+", " ".join(cells))
    if len(nums) >= 7:
        # 6项种族值+总和
        pet["hp"] = int(nums[0])
        pet["atk"] = int(nums[1])
        pet["defense"] = int(nums[2])
        pet["sp_atk"] = int(nums[3])
        pet["sp_def"] = int(nums[4])
        pet["speed"] = int(nums[5])
        pet["total"] = int(nums[6]) if len(nums) > 6 else sum(nums[:6])
    elif len(nums) == 1:
        pet["total"] = int(nums[0])

    # 识别属性
    types = ["普通", "草", "火", "水", "光", "地", "冰", "龙",
             "电", "幻", "毒", "虫", "翼", "恶", "萌", "幽灵", "武"]
    for t in types:
        if t in " ".join(cells):
            if "type_primary" not in pet:
                pet["type_primary"] = t
            elif pet.get("type_primary") != t and "type_secondary" not in pet:
                pet["type_secondary"] = t

    return pet if len(pet) > 1 else None


def extract_pets_from_text(text: str) -> list[dict]:
    """从长文本中提取精灵数据。"""
    pets = []
    # 匹配 名称(种族值) 或 名称：属性，种族值=xxx
    # 洛克王国常见的写法
    patterns = [
        r'([一-鿿]{2,6})\s*[（(](\d+)[）)]',  # 名称(种族值)
        r'([一-鿿]{2,6})[：:]\s*(\w+系)',    # 名称：属性系
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            pets.append({"name": m[0], "raw_field": m[1] if len(m) > 1 else ""})
    return pets


def extract_pet_from_block(text: str) -> dict | None:
    """从单个文本块提取精灵数据。"""
    # 必须包含精灵名（中文2-6字）和至少一个数字
    name_match = re.search(r"([一-鿿]{2,6})", text)
    num_match = re.search(r"\d{2,4}", text)
    if name_match and num_match:
        return {"name": name_match.group(1), "raw": text}
    return None


def scrape_ninegame_pets(url: str) -> list[dict]:
    """从九游网抓取精灵数据。"""
    soup = fetch_html(url)
    if not soup:
        return []

    pets = []
    # 查找图鉴内容区域
    for article in soup.find_all(["article", "div"], class_=re.compile(r"content|article|detail")):
        paragraphs = article.find_all(["p", "h3", "h4", "li"])
        for p in paragraphs:
            text = p.get_text(strip=True)
            extracted = extract_pet_from_block(text)
            if extracted:
                pets.append(extracted)
    return pets


def cross_validate(bwiki_data: list[dict], external_data: list[dict]) -> list[dict]:
    """
    交叉验证：将外部数据源的数据与 BWIKI 数据合并。
    - 同名精灵，外部数据补充 BWIKI 缺失字段
    - BWIKI 没有的精灵，从外部数据添加（标记来源）
    """
    bwiki_by_name = {}
    for pet in bwiki_data:
        name = pet.get("name", "")
        if name:
            bwiki_by_name[name] = pet

    for ext in external_data:
        ext_name = ext.get("name", "")
        if not ext_name:
            continue

        if ext_name in bwiki_by_name:
            # 补充缺失字段
            existing = bwiki_by_name[ext_name]
            for key, val in ext.items():
                if key != "name" and (not existing.get(key)):
                    existing[key] = val
                    existing[f"{key}_source"] = "external"
        else:
            # 新精灵
            ext["source"] = "external_only"
            bwiki_by_name[ext_name] = ext

    return list(bwiki_by_name.values())


def scrape_all_external() -> list[dict]:
    """抓取所有外部数据源，返回合并后的精灵列表。"""
    from config import BIUBIU_PETS, NINEGAME

    all_external = []

    print("  抓取 biubiu001...")
    biubiu_pets = scrape_biubiu_article(BIUBIU_PETS)
    all_external.extend(biubiu_pets)
    print(f"    获取 {len(biubiu_pets)} 条")

    time.sleep(REQUEST_DELAY)

    print("  抓取 九游网...")
    ninegame_pets = scrape_ninegame_pets(NINEGAME)
    all_external.extend(ninegame_pets)
    print(f"    获取 {len(ninegame_pets)} 条")

    # 去重
    seen = set()
    unique = []
    for pet in all_external:
        name = pet.get("name", "")
        if name and name not in seen:
            seen.add(name)
            unique.append(pet)

    print(f"  外部数据总计(去重): {len(unique)} 条")

    save_path = Path(RAW_DIR) / "external_raw.json"
    save_path.parent.mkdir(parents=True, exist_ok=True)
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)

    return unique


if __name__ == "__main__":
    external = scrape_all_external()
    print(f"\n共获取 {len(external)} 条外部数据")

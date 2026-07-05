"""
洛克王国：世界 官方网站爬虫

数据源: https://rocom.qq.com/web202507/sub/index.html (腾讯官方站点)
角色: 权威数据确认源 (Level 1)

说明:
  该站点为腾讯魔方工作室群自主研发的《洛克王国：世界》官方网站，
  主要以交互式单页应用(SPA)形式呈现，不适合传统爬虫直接抓取结构化数据。

  本模块策略:
    - 定期检查官方站点是否有新的内容更新（版本号、精灵数量等）
    - 从页面 meta 信息中提取基础游戏数据
    - 对比官网数据与 BWIKI 数据的一致性
    - 当官网发布新内容时触发数据更新告警

  官方站点信息 (截至 2026-06):
    - 游戏状态: 已正式上线 (2026.3.26 全平台)
    - 当前赛季: S2「狂欢怪谈」(2026.5.21 - 7.15)
    - 下个赛季: S3「威廉古堡」(2026.7.16 起)
    - 游戏类型: 精灵收集 + 开放世界 RPG
    - 精灵数量: 400+ 只免费捕捉
    - 平台: 多端互通 (iOS + Android + PC)
    - 特色: 多体系战斗、自由社交、家园系统

  赛季更迭:
    - S1「暗夜拾光」: 2026.3.26 - 5.20, 传说精灵 龙息帕尔(恶), 噩梦枷锁机制
    - S2「狂欢怪谈」: 2026.5.21 - 7.15, 传说精灵 机幕方舟(机械), 拼装传动/幸运惊喜盒
    - S3「威廉古堡」: 2026.7.16 起, 传说精灵 灵蔓草王, 新地图+新首领战"""
"""

import re
import json
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from config import OFFICIAL_SITE, OFFICIAL_BASE, RAW_DIR


def _make_session() -> requests.Session:
    """创建请求会话。"""
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    })
    return s


def check_availability() -> dict:
    """
    检查官方站点是否可访问，并提取基础元数据。

    Returns:
        {
            "accessible": bool,
            "status_code": int,
            "title": str,
            "meta_keywords": str,
            "meta_description": str,
            "timestamp": str,
        }
    """
    result = {
        "accessible": False,
        "status_code": 0,
        "title": "",
        "meta_keywords": "",
        "meta_description": "",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    try:
        session = _make_session()
        resp = session.get(OFFICIAL_SITE, timeout=30)
        result["status_code"] = resp.status_code

        if resp.status_code == 200:
            result["accessible"] = True
            soup = BeautifulSoup(resp.text, "lxml")

            # 提取标题
            title_tag = soup.find("title")
            if title_tag:
                result["title"] = title_tag.get_text(strip=True)

            # 提取 meta 信息
            for meta_name in ["keywords", "description"]:
                meta = soup.find("meta", attrs={"name": meta_name})
                if meta:
                    result[f"meta_{meta_name}"] = meta.get("content", "")

    except requests.RequestException as e:
        result["error"] = str(e)

    return result


def extract_game_info() -> dict:
    """
    从官方站点页面内容中提取游戏信息。
    当前为占位实现 — 待官网有可读数据后再完善。
    """
    info = {
        "source": OFFICIAL_SITE,
        "source_type": "official",
        "confidence": "authoritative",
        "game_name": "洛克王国：世界",
        "developer": "腾讯魔方工作室群",
        "publisher": "腾讯",
        "genres": ["精灵收集", "开放世界", "回合制对战", "RPG"],
        "platforms": ["iOS", "Android", "PC"],
        "total_pets_official": 400,  # 官网宣称 400+ 只
        "features": [
            "多体系战斗（攻击/状态/防御 三角克制）",
            "400+精灵免费收集",
            "开放世界探索",
            "多端互通",
            "自由社交",
            "家园系统",
            "孵蛋系统",
        ],
    }
    return info


def scrape_pets():
    """
    官方站点爬虫入口。

    注意：该官方站点使用 JavaScript 渲染数据，传统 HTML 解析无法获取
    完整的精灵/技能列表。当前实现用于监控站点可用性和元数据变化。
    完整数据获取仍以 BWIKI API 为主。
    """
    print("=" * 50)
    print("官方站点检查 (rocom.qq.com)")
    print("=" * 50)

    # 1. 检查可用性
    print("\n[1] 检查官方站点可访问性...")
    status = check_availability()
    print(f"  可访问: {'是' if status['accessible'] else '否'}")
    print(f"  HTTP状态: {status['status_code']}")
    if status.get("title"):
        print(f"  标题: {status['title']}")
    if status.get("error"):
        print(f"  错误: {status['error']}")

    # 2. 提取游戏元信息
    print("\n[2] 提取官方信息...")
    info = extract_game_info()
    print(f"  游戏: {info['game_name']}")
    print(f"  开发商: {info['developer']}")
    print(f"  官方精灵数量: {info['total_pets_official']}+ 只")

    # 3. 保存
    print("\n[3] 保存官方数据...")
    Path(RAW_DIR).mkdir(parents=True, exist_ok=True)

    with open(Path(RAW_DIR) / "official_site_status.json", "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

    with open(Path(RAW_DIR) / "official_game_info.json", "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)

    print(f"  已保存到 {RAW_DIR}/official_*.json")

    # 官方站点目前不产出精灵/技能数据（由 BWIKI 负责）
    return [], {}


if __name__ == "__main__":
    scrape_pets()

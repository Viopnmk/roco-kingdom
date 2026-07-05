"""
洛克王国：世界 数据爬虫 —— 主入口

数据源层次:
  Level 1 (权威): https://rocom.qq.com/web202507/sub/index.html — 腾讯官方站点
  Level 2 (主要): https://wiki.biligame.com/rocom/ — BWIKI 社区百科
  Level 3 (备用): 攻略站/LCX 等 — 交叉验证用

用法:
    python main.py                  # 完整流程: 爬取全部启用源 → 清洗
    python main.py --scrape         # 仅爬取（跳过清洗管道）
    python main.py --pipeline       # 仅清洗（需要已爬取的数据）
    python main.py --probe          # 探测 BWIKI 页面结构（调试用）

新增数据源:
    1. 在 spiders/ 下新建爬虫模块，实现 scrape() 函数
    2. 在 config.py 的 SOURCES 中注册（注明 level）
    3. 运行 python main.py
"""

import sys
import argparse
import importlib
import json
from pathlib import Path

from config import SOURCES, RAW_DIR, BATCH_SIZE
from pipeline import run_pipeline


def run_all_sources() -> bool:
    """遍历所有启用的数据源并执行爬取。返回是否有任何数据产出。"""
    any_data = False

    for source_id, cfg in SOURCES.items():
        if not cfg.get("enabled", False):
            print(f"\n>>> [{cfg['name']}] 已禁用，跳过")
            continue

        print(f"\n{'=' * 50}")
        level = cfg.get("level", "?")
        print(f">>> [Lv{level} {cfg['name']}] 开始爬取")
        print(f"{'=' * 50}")

        try:
            mod = importlib.import_module(cfg["module"])
            # 各爬虫模块需实现 scrape_pets() → (pets_list, skills_dict)
            result = mod.scrape_pets()
            if result:
                pets, skills = result
                if pets:
                    any_data = True
                    print(f"  [{cfg['name']}] 完成: {len(pets)} 只精灵, {len(skills)} 个技能")
        except ImportError as e:
            print(f"  [ERROR] 加载模块 {cfg['module']} 失败: {e}")
        except AttributeError:
            print(f"  [ERROR] 模块 {cfg['module']} 缺少 scrape_pets() 函数")
        except Exception as e:
            print(f"  [ERROR] {cfg['name']} 爬取出错: {e}")

    return any_data


def probe():
    """探测 BWIKI 页面结构，保存样本供分析。"""
    import time

    print("探测 BWIKI 页面结构...")
    # 先尝试发现页面
    from spiders.bwiki import discover_pet_pages, get_page_wikitext, parse_templates

    titles = discover_pet_pages()
    if not titles:
        print("未发现页面")
        return

    sample_size = min(5, len(titles))
    samples = {}
    for title in titles[:sample_size]:
        print(f"  探测: {title}")
        wikitext = get_page_wikitext(title)
        if wikitext:
            templates = parse_templates(wikitext)
            relevant = [t for t in templates if any(
                kw in t["name"].lower()
                for kw in ["宠物", "精灵", "信息", "infobox", "pet"]
            )]
            samples[title] = {
                "relevant_templates": relevant,
                "all_template_names": [t["name"] for t in templates],
            }
        time.sleep(1.0)

    probe_path = Path(RAW_DIR) / "probe_samples.json"
    probe_path.parent.mkdir(parents=True, exist_ok=True)
    with open(probe_path, "w", encoding="utf-8") as f:
        json.dump(samples, f, ensure_ascii=False, indent=2)
    print(f"  样本已保存: {probe_path}")
    print(f"  模板名称: {[t['name'] for s in samples.values() for t in s.get('all_template_names', [])]}")


def main():
    parser = argparse.ArgumentParser(description="洛克王国：世界 数据爬虫")
    parser.add_argument("--scrape", action="store_true", help="仅爬取数据（跳过清洗）")
    parser.add_argument("--pipeline", action="store_true", help="仅运行数据清洗管道")
    parser.add_argument("--probe", action="store_true", help="探测 BWIKI 页面结构")
    args = parser.parse_args()

    if args.probe:
        probe()
        return

    if args.pipeline:
        run_pipeline()
        return

    # 爬取
    print("\n启用数据源:")
    for sid, cfg in SOURCES.items():
        mark = "[ON]" if cfg["enabled"] else "[OFF]"
        level = cfg.get("level", "?")
        print(f"  {mark} [Lv{level}] {cfg['name']}")

    has_data = run_all_sources()

    if args.scrape:
        print("\n跳过数据清洗（--scrape 模式）")
        return

    # 清洗
    if has_data:
        print("\n>>> 数据清洗")
        run_pipeline()
    else:
        print("\n[WARN] 没有爬取到任何数据，跳过清洗")

    print("\n全部完成! 数据保存到 scraper/output/ 目录")


if __name__ == "__main__":
    main()

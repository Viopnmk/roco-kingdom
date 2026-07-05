"""
数据同步脚本 —— 将 scraper/output 中的 JSON 数据复制到 web/src/data/
用法: python sync_data.py
"""

import json
import shutil
from pathlib import Path

SCRAPER_OUTPUT = Path("../scraper/output")
ML_DATA = Path("../ml/data")
WEB_DATA = Path("src/data")

FILES = ["pets.json", "skills.json", "learnset.json", "type_chart.json", "stats.json"]
ML_FILES = ["evolution_chains.json"]


def sync():
    """同步数据文件。"""
    if not SCRAPER_OUTPUT.exists():
        print("[ERROR] 找不到 scraper/output/ 目录，请先运行爬虫")
        print("  cd ../scraper && pip install -r requirements.txt && python main.py")
        return

    WEB_DATA.mkdir(parents=True, exist_ok=True)

    for fname in FILES:
        src = SCRAPER_OUTPUT / fname
        dst = WEB_DATA / fname
        if src.exists():
            shutil.copy2(src, dst)
            print(f"  [OK] {fname}")
        else:
            print(f"  [SKIP] {fname} (不存在)")

    for fname in ML_FILES:
        src = ML_DATA / fname
        dst = WEB_DATA / fname
        if src.exists():
            shutil.copy2(src, dst)
            print(f"  [OK] {fname} (from ml/data/)")
        else:
            print(f"  [SKIP] {fname} (不存在)")

    # 从进化链数据中提取候选ID，生成轻量文件
    _extract_candidate_ids()

    print("\n同步完成!")


def _extract_candidate_ids():
    """从 evolution_chains.json 提取 candidate_ids：
    1. 过滤到 pets.json 中实际存在的精灵
    2. 排除独立链中与其他链前阶形态同名的重复条目（BWIKI 数据重复问题）
    """
    evo_path = WEB_DATA / "evolution_chains.json"
    pets_path = WEB_DATA / "pets.json"
    if not evo_path.exists():
        print("  [SKIP] candidate_ids.ts (evolution_chains.json 不存在)")
        return

    with open(evo_path, "r", encoding="utf-8") as f:
        evo = json.load(f)
    with open(pets_path, "r", encoding="utf-8") as f:
        pets = json.load(f)

    pet_id_set = {p["id"] for p in pets}

    # 收集多成员链中非顶端精灵的名称（即确定的前阶形态）
    pre_evo_names: set[str] = set()
    for c in evo.get("chains", []):
        if len(c.get("members", [])) <= 1:
            continue
        apex = c["apex_id"]
        for i, mid in enumerate(c["members"]):
            if mid != apex:
                pre_evo_names.add(c["member_names"][i])

    raw_ids = evo.get("candidate_ids", [])
    # 建立 ID -> 名称 的映射（从进化链中查找）
    id_to_name: dict[int, str] = {}
    for c in evo.get("chains", []):
        for i, mid in enumerate(c["members"]):
            id_to_name[mid] = c["member_names"][i]

    valid_ids = []
    dup_excluded = 0
    missing_excluded = 0

    for mid in raw_ids:
        if mid not in pet_id_set:
            missing_excluded += 1
            continue
        name = id_to_name.get(mid, "")
        # 如果是独立链的顶端，但同名精灵在其他链中是前阶 → 排除
        if name and name in pre_evo_names:
            dup_excluded += 1
            continue
        valid_ids.append(mid)

    valid_ids.sort()
    ts_path = WEB_DATA / "candidate_ids.ts"
    content = (
        "// 自动生成 — 候选ID ∩ pets.json，已排除重复前阶形态\n"
        f"// 原始候选 {len(raw_ids)} → 过滤后 {len(valid_ids)} 只\n"
        f"// （排除缺失 {missing_excluded} + 重复前阶 {dup_excluded}）\n"
        f"// 运行 sync_data.py 重新生成\n"
        f"export const APEX_IDS: Set<number> = new Set({json.dumps(valid_ids)});\n"
    )
    with open(ts_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  [OK] candidate_ids.ts ({len(valid_ids)} 个顶端ID, "
          f"排除缺失{missing_excluded}+重复前阶{dup_excluded})")

    # 回写过滤后的候选池到 ml/data/evolution_chains.json（API 使用）
    evo["candidate_ids"] = valid_ids
    evo["candidate_pool_size"] = len(valid_ids)
    evo["_filtered_by_sync"] = True
    ml_evo_path = ML_DATA / "evolution_chains.json"
    with open(ml_evo_path, "w", encoding="utf-8") as f:
        json.dump(evo, f, ensure_ascii=False, indent=2)
    print(f"  [OK] ml/data/evolution_chains.json (candidate_ids 已更新为 {len(valid_ids)} 个)")


def update_index_ts():
    """更新 data/index.ts 改用动态 import JSON。"""
    # 保持原有占位结构，让用户自行替换为 import
    pass


if __name__ == "__main__":
    sync()

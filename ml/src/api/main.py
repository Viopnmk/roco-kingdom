"""
FastAPI 应用入口 — 洛克王国 AI 配队助手 API

启动方式（从 ml/ 目录）：
    uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 将 ml/src/ 添加到 sys.path，确保模块导入正常
_src = Path(__file__).resolve().parents[1]  # ml/src/
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from .routes import router  # noqa: E402


# ══════════════════════════════════════════════════════════════════════
# 数据预加载
# ══════════════════════════════════════════════════════════════════════

def _load_all_data(base: Path) -> dict:
    """启动时一次性加载全部数据到内存，构建 O(1) 查表索引。"""
    print("[Startup] Loading data files...")

    # ── 精灵画像 ──
    with open(base / "ml" / "data" / "pet_profiles.json", "r", encoding="utf-8") as f:
        profiles_list = json.load(f)
    profiles_dict: Dict[int, dict] = {p["id"]: p for p in profiles_list}
    print(f"  [OK] pet_profiles: {len(profiles_list)} pets")

    # ── 联动图 ──
    with open(base / "ml" / "data" / "synergy_graph.json", "r", encoding="utf-8") as f:
        synergy_data = json.load(f)

    # 预建 O(1) 联动得分索引
    synergy_dict: Dict[Tuple[int, int], float] = {}
    for pair in synergy_data.get("pairs", []):
        a, b = pair["pet_a_id"], pair["pet_b_id"]
        synergy_dict[(min(a, b), max(a, b))] = pair["score"]
    synergy_highlights = synergy_data.get("top_highlights", [])
    print(f"  [OK] synergy_graph: {len(synergy_dict)} pairs, "
          f"{len(synergy_highlights)} highlights")

    # ── 属性克制表 ──
    with open(base / "scraper" / "output" / "type_chart.json", "r", encoding="utf-8") as f:
        type_chart = json.load(f)["chart"]
    print(f"  [OK] type_chart: {len(type_chart)} attack types")

    # ── 候选池过滤（与 sync_data.py 逻辑一致）────────────────
    evo_path = base / "ml" / "data" / "evolution_chains.json"
    if evo_path.exists():
        with open(evo_path, "r", encoding="utf-8") as f:
            evo_data = json.load(f)
        raw_candidate_ids = evo_data.get("candidate_ids", [])
        print(f"  [OK] evolution_chains: {evo_data.get('total_chains', 0)} chains, "
              f"{len(raw_candidate_ids)} raw candidates "
              f"(excl. {len(evo_data.get('boss_excluded', []))} boss)")
    else:
        raw_candidate_ids = [p["id"] for p in profiles_list]
        evo_data = {"chains": []}
        print("  [--] evolution_chains not found, using all pets")

    # 收集多成员链中非顶端精灵的名称（用于排除假顶端）
    pre_evo_names: set = set()
    id_to_name: dict = {}
    for c in evo_data.get("chains", []):
        members = c.get("members", [])
        names = c.get("member_names", [])
        apex = c.get("apex_id")
        for i, mid in enumerate(members):
            if i < len(names):
                id_to_name[mid] = names[i]
        if len(members) > 1 and apex:
            for i, mid in enumerate(members):
                if mid != apex and i < len(names):
                    pre_evo_names.add(names[i])

    profile_id_set = {p["id"] for p in profiles_list}

    # 过滤候选池
    candidate_ids = []
    missing_count = 0
    dup_count = 0
    for mid in raw_candidate_ids:
        if mid not in profile_id_set:
            missing_count += 1
            continue
        name = id_to_name.get(mid, "")
        if name and name in pre_evo_names:
            dup_count += 1
            continue
        candidate_ids.append(mid)

    # 仅候选池内的精灵参与搜索
    candidate_set = set(candidate_ids)
    pet_ids = candidate_ids
    pet_skills: Dict[int, List[str]] = {}
    for p in profiles_list:
        if p["id"] in candidate_set:
            pet_skills[p["id"]] = p.get("optimal_skills", [])[:]
    print(f"  [OK] candidate pool: {len(candidate_ids)} apex pets "
          f"(excluded {missing_count} missing + {dup_count} duplicate pre-evo), "
          f"{len(pet_skills)} skill maps")

    print("[Startup] Data loaded successfully.")
    return {
        "profiles_list": profiles_list,
        "profiles_dict": profiles_dict,
        "synergy_pairs": synergy_data.get("pairs", []),
        "synergy_dict": synergy_dict,
        "synergy_highlights": synergy_highlights,
        "type_chart": type_chart,
        "pet_ids": pet_ids,
        "pet_skills": pet_skills,
    }


# ══════════════════════════════════════════════════════════════════════
# 应用生命周期
# ══════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：加载数据
    base = Path(__file__).resolve().parents[3]  # 洛克王国/ 项目根
    data = _load_all_data(base)
    for key, value in data.items():
        setattr(app.state, key, value)
    yield
    # 关闭：无需清理（数据在内存中随进程结束释放）


# ══════════════════════════════════════════════════════════════════════
# 创建应用
# ══════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="洛克王国 AI 配队助手 API",
    description="""## 精灵图鉴 × AI 配队引擎

基于 **375 精灵 / 494 技能 / 18 属性体系**，提供：

| 端点 | 说明 |
|------|------|
| **POST** `/api/optimize` | 多目标遗传算法搜索最优 6 精灵配队 |
| **GET** `/api/pet/{id}/profile` | 精灵完整画像（种族值/打击面/抗性面/职责） |
| **GET** `/api/synergy/{a}/{b}` | 双精灵联动分析（得分 + 互补理由） |

支持约束条件：必含精灵、排除精灵、偏好属性、战术风格（灼烧/中毒/冻结/星陨/天气/传动）。
""",
    version="0.2.0",
    lifespan=lifespan,
)

# CORS — 允许前端开发服务器跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


# ══════════════════════════════════════════════════════════════════════
# 直接启动入口
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    print("启动方式（推荐从 ml/ 目录运行）：")
    print("  cd ml/")
    print("  uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000")
    print()
    print("尝试直接启动...")
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )

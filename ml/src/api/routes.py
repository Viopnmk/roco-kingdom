"""
FastAPI 路由 — 配队优化 / 精灵画像 / 联动查询
"""

import asyncio
from fastapi import APIRouter, Request, HTTPException

from .schemas import (
    OptimizeRequest, OptimizeResponse, OptimizeResult,
    PetProfileResponse, PetStats,
    PetBrief, SynergyResponse,
)
from ..optimize.fitness import TeamFitness
from ..optimize import genetic

router = APIRouter(prefix="/api")


# ── 辅助：取预加载数据 ──────────────────────────────────────────────

def _state(request: Request):
    return request.app.state


# ── POST /api/optimize ──────────────────────────────────────────────

@router.post("/optimize", response_model=OptimizeResponse)
async def optimize(req: OptimizeRequest, request: Request):
    """
    多目标遗传算法搜索最优 6 精灵配队。

    支持约束：必含/排除精灵、偏好属性、战术风格、最少打击面覆盖。
    返回 Top-K 队伍及 7 维分数分解。
    """
    state = _state(request)

    # 构造适应度引擎（轻量包装，O(1) 引用复用预加载数据）
    engine = TeamFitness(
        state.profiles_list,
        state.synergy_pairs,
        state.type_chart,
    )

    # CPU 密集型的遗传算法放到线程池，避免阻塞事件循环
    results = await asyncio.to_thread(
        genetic.optimize,
        fitness_engine=engine,
        pet_ids=state.pet_ids,
        pet_skills=state.pet_skills,
        must_include=req.must_include,
        must_exclude=req.must_exclude,
        prefer_type=req.prefer_type,
        style=req.style,
        team_type=req.team_type if req.team_type else None,
        min_coverage=req.min_coverage,
        top_k=req.top_k,
        pop_size=req.pop_size,
        generations=req.generations,
        verbose=False,
    )

    return OptimizeResponse(
        teams=[OptimizeResult(**r) for r in results],
        generations=req.generations,
        pop_size=req.pop_size,
    )


# ── GET /api/pet/{pet_id}/profile ───────────────────────────────────

@router.get("/pet/{pet_id}/profile", response_model=PetProfileResponse)
async def pet_profile(pet_id: int, request: Request):
    """查询一只精灵的完整画像：种族值、打击面、抗性面、职责、最优技能等。"""
    state = _state(request)
    pet = state.profiles_dict.get(pet_id)
    if not pet:
        raise HTTPException(status_code=404, detail=f"精灵 #{pet_id} 不存在")

    return PetProfileResponse(
        id=pet["id"],
        name=pet["name"],
        type_primary=pet["type_primary"],
        type_secondary=pet.get("type_secondary"),
        stats=PetStats(
            hp=pet["stat_hp"],
            atk=pet["stat_atk"],
            defense=pet["stat_def"],
            sp_atk=pet["stat_sp_atk"],
            sp_def=pet["stat_sp_def"],
            speed=pet["stat_speed"],
        ),
        stat_total=pet["stat_total"],
        effective_atk=pet["effective_atk"],
        effective_sp_atk=pet["effective_sp_atk"],
        effective_def=pet["effective_def"],
        effective_sp_def=pet["effective_sp_def"],
        effective_speed=pet["effective_speed"],
        effective_hp=pet["effective_hp"],
        role=pet["role"],
        attack_preference=pet["attack_preference"],
        optimal_skills=pet["optimal_skills"],
        physical_skill_count=pet["physical_skill_count"],
        magic_skill_count=pet["magic_skill_count"],
        status_skill_count=pet["status_skill_count"],
        coverage_vector=pet["coverage_vector"],
        weakness_vector=pet["weakness_vector"],
        avg_energy_cost=pet["avg_energy_cost"],
        has_energy_recovery=pet["has_energy_recovery"],
        synergy_tags=pet["synergy_tags"],
        ability=pet.get("ability", ""),
    )


# ── GET /api/synergy/{pet_id_a}/{pet_id_b} ──────────────────────────

@router.get("/synergy/{pet_id_a}/{pet_id_b}", response_model=SynergyResponse)
async def synergy(pet_id_a: int, pet_id_b: int, request: Request):
    """查询两只精灵之间的联动得分与互补理由。"""
    state = _state(request)

    pet_a = state.profiles_dict.get(pet_id_a)
    pet_b = state.profiles_dict.get(pet_id_b)
    if not pet_a:
        raise HTTPException(status_code=404, detail=f"精灵 #{pet_id_a} 不存在")
    if not pet_b:
        raise HTTPException(status_code=404, detail=f"精灵 #{pet_id_b} 不存在")

    # 查联动得分（O(1) dict 查找）
    key = (min(pet_id_a, pet_id_b), max(pet_id_a, pet_id_b))
    score = state.synergy_dict.get(key, 0.0)

    # 查高亮原因（按名称匹配）
    highlights = None
    lookup = (pet_a["name"], pet_b["name"])
    rev_lookup = (pet_b["name"], pet_a["name"])
    for h in state.synergy_highlights:
        if (h["pet_a"], h["pet_b"]) in (lookup, rev_lookup):
            if highlights is None:
                highlights = []
            highlights.append(h)

    return SynergyResponse(
        pet_a=_make_brief(pet_a),
        pet_b=_make_brief(pet_b),
        synergy_score=round(score, 1),
        highlights=highlights,
    )


def _make_brief(pet: dict) -> PetBrief:
    return PetBrief(
        id=pet["id"],
        name=pet["name"],
        type_primary=pet["type_primary"],
        type_secondary=pet.get("type_secondary"),
        role=pet["role"],
        synergy_tags=pet["synergy_tags"],
    )

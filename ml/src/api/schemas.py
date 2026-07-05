"""
Pydantic v2 请求/响应模型 — FastAPI 数据校验 & OpenAPI 文档
"""

from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict


# ── Optimize ────────────────────────────────────────────────────────

class OptimizeRequest(BaseModel):
    """配队优化请求参数。"""
    must_include: Optional[List[int]] = Field(default=None, description="必须包含的精灵ID列表")
    must_exclude: Optional[List[int]] = Field(default=None, description="排除的精灵ID列表")
    prefer_type: Optional[str] = Field(default=None, description="偏好属性（如'火'、'水'）")
    style: Optional[str] = Field(
        default=None,
        description="战术风格：灼烧体系 / 中毒消耗 / 冻结控场 / 星陨爆发 / 天气队 / 传动体系 / 印记运营 / 应对返还 / 先手压制 / 吸血续航 / 增益传递 / 巧变切换 / 萌化退化",
    )
    team_type: Optional[str] = Field(
        default=None,
        description="配队类型：synergy=体系队(单属性核心+技能联动), balanced=平衡队(属性分散+广泛打击面)",
    )
    min_coverage: float = Field(default=0.0, ge=0.0, le=100.0, description="最低打击面覆盖分")
    top_k: int = Field(default=10, ge=1, le=50, description="返回最优队伍数量")
    pop_size: int = Field(default=100, ge=20, le=500, description="种群大小")
    generations: int = Field(default=100, ge=20, le=500, description="进化代数")


class PetStats(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    hp: int
    atk: int
    defense: int = Field(validation_alias="def", serialization_alias="def")
    sp_atk: int
    sp_def: int
    speed: int


class TeamMember(BaseModel):
    pet_id: int
    name: str
    type_primary: str
    type_secondary: Optional[str] = None
    role: str
    skills: List[str]
    stats: PetStats


class TeamScores(BaseModel):
    coverage: float
    defense: float
    synergy: float
    stats: float
    role_balance: float
    speed: float
    energy: float
    total: float


class OptimizeResult(BaseModel):
    team: List[TeamMember]
    scores: TeamScores


class OptimizeResponse(BaseModel):
    teams: List[OptimizeResult]
    generations: int
    pop_size: int


# ── Pet Profile ─────────────────────────────────────────────────────

class PetProfileResponse(BaseModel):
    id: int
    name: str
    type_primary: str
    type_secondary: Optional[str] = None
    stats: PetStats
    stat_total: int
    effective_atk: int
    effective_sp_atk: int
    effective_def: int
    effective_sp_def: int
    effective_speed: int
    effective_hp: int
    role: str
    attack_preference: str
    optimal_skills: List[str]
    physical_skill_count: int
    magic_skill_count: int
    status_skill_count: int
    coverage_vector: Dict[str, float]
    weakness_vector: Dict[str, float]
    avg_energy_cost: float
    has_energy_recovery: bool
    synergy_tags: List[str]
    ability: str


# ── Synergy ─────────────────────────────────────────────────────────

class PetBrief(BaseModel):
    id: int
    name: str
    type_primary: str
    type_secondary: Optional[str] = None
    role: str
    synergy_tags: List[str]


class SynergyResponse(BaseModel):
    pet_a: PetBrief
    pet_b: PetBrief
    synergy_score: float = 0.0
    highlights: Optional[List[Dict[str, object]]] = None

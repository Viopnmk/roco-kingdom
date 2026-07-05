"""
精灵-技能超图 & 联动得分矩阵

输入: pet_profiles.json + parsed_skills.json + type_chart.json
输出: ml/data/synergy_graph.json

算法:
  对每对精灵 (A, B):
    1. 异常状态联动: A施加灼烧 → B引爆灼烧 = +30分
    2. 天气联动: A设天气 → B受益 = +25分
    3. 抗性互补: B能打A的弱点 → +8分
    4. 标签重叠: 共享的战术标签 → +6/+3分/个
    5. 应对链: A的应对类型缺失由B补齐 → +12分
    6. 特性状态联动: A特性有状态联动 + B能施加该状态 → +20分
    7. 特性应对联动: 双方特性都有应对增强 → +15分
    8. 特性印记联动: 双方特性都有印记联动 → +18分
    9. 特性入场退场链: A退场效果 + B入场效果 → +12分
   10. 特性蓄力迸发联动: 双方都有蓄力联动 → +12分
   11. 特性天气联动: A特性天气联动 + B能设置天气 → +15分
   12. 特性能量循环: A回能 + B降耗 → +15分
"""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Set, Optional
from collections import defaultdict

# 导入特性标注器
import sys
_src = Path(__file__).resolve().parents[1]  # ml/src/
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))
from parser.ability_tagger import tag_ability


# ── 联动规则 ──────────────────────────────────────────────────────

# 状态施予 → 状态利用的映射
STATUS_SYNERGY = {
    "灼烧": ["灼烧"],
    "中毒": ["中毒"],
    "冻结": ["冻结"],
    "星陨": ["星陨"],
    "萌化": ["萌化"],
    "寄生": ["寄生"],
}

# 天气受益属性
WEATHER_BENEFIT = {
    "暴风雪": "冰",
    "沙暴": "地",
    "雨天": "水",
}


# ── ML 联动矩阵 ────────────────────────────────────────────────────

def compute_ml_synergy_matrix(
    profiles: List[dict],
    pet_embeddings: Dict[int, np.ndarray],
) -> np.ndarray:
    """
    基于精灵 embedding 余弦相似度的纯 ML 联动矩阵。

    embedding 已 L2 归一化，dot(i, j) = cosine_sim(i, j)。
    将相似度映射到 0-100 范围，阈值为 0.25（低于此值视为无联动）。
    """
    n = len(profiles)
    matrix = np.zeros((n, n), dtype=np.float32)
    id_to_idx = {p["id"]: i for i, p in enumerate(profiles)}

    # 组装矩阵
    ids = [p["id"] for p in profiles]
    dim = 384
    vecs = np.zeros((n, dim), dtype=np.float32)
    for i, pid in enumerate(ids):
        vecs[i] = pet_embeddings.get(pid, np.zeros(dim, dtype=np.float32))

    # 余弦相似度（向量已归一化）
    sim_matrix = vecs @ vecs.T  # (N, N)

    # 映射到 0-100 联动分：sim > 0.25 开始有效
    ml_synergy = np.clip((sim_matrix - 0.25) / 0.75 * 100.0, 0.0, 100.0)
    return ml_synergy


def compute_synergy_matrix(
    profiles: List[dict],
    type_chart: dict,
    pet_embeddings: Optional[Dict[int, np.ndarray]] = None,
    ml_weight: float = 0.30,
) -> Tuple[np.ndarray, List[dict]]:
    """
    计算 375×375 联动得分矩阵（规则引擎 + 可选 ML 融合）。

    Args:
        pet_embeddings: 精灵 NLP embedding 字典（可选，None 则纯规则）
        ml_weight: ML 联动分权重（0.0=纯规则，1.0=纯ML）

    Returns:
        matrix: (N, N) float32 联动得分矩阵
        highlights: 每对高联动精灵的说明文字
    """
    n = len(profiles)
    matrix = np.zeros((n, n), dtype=np.float32)
    highlights: List[dict] = []

    # 建立索引
    id_to_idx = {p["id"]: i for i, p in enumerate(profiles)}

    # 预提取每只精灵的特征
    pet_status_appliers: Dict[int, Set[str]] = {}     # 施加的状态
    pet_status_users: Dict[int, Set[str]] = {}         # 利用的状态
    pet_weather_setters: Dict[int, str] = {}            # 设置的天气
    pet_weather_types: Dict[int, str] = {}             # 精灵属性（判断天气受益）
    pet_weaknesses: Dict[int, Set[str]] = {}           # 弱点（被克制≥2x的属性）
    pet_coverages: Dict[int, Set[str]] = {}            # 能打≥2x的属性
    pet_tags: Dict[int, Set[str]] = {}                 # 联动标签
    pet_ability_tags: Dict[int, Set[str]] = {}         # 特性机械标签
    pet_ability_text: Dict[int, str] = {}              # 特性原始文本

    for p in profiles:
        pid = p["id"]
        tags = set(p.get("synergy_tags", []))

        # 状态施予
        appliers = set()
        users = set()
        for tag, related in STATUS_SYNERGY.items():
            if tag in tags:
                appliers.add(tag)
                users.add(tag)
        pet_status_appliers[pid] = appliers
        pet_status_users[pid] = users

        # 天气
        wt = "暴风雪" if "暴风雪" in tags else ("沙暴" if "沙暴" in tags else ("雨天" if "雨天" in tags else ""))
        if wt:
            pet_weather_setters[pid] = wt
        pet_weather_types[pid] = p.get("type_primary", "")

        # 弱点: 被≥2x克制的属性
        weak = set()
        wv = p.get("weakness_vector", {})
        for atk_type, mult in wv.items():
            if mult >= 2.0:
                weak.add(atk_type)
        pet_weaknesses[pid] = weak

        # 打击面: 能打≥2x的属性
        cov = set()
        cv = p.get("coverage_vector", {})
        for def_type, mult in cv.items():
            if mult >= 2.0:
                cov.add(def_type)
        pet_coverages[pid] = cov

        pet_tags[pid] = tags

        # ── 特性标签 ──
        ability = p.get("ability", "")
        pet_ability_text[pid] = ability
        pet_ability_tags[pid] = set(tag_ability(ability))

    # 计算矩阵
    for i, p_a in enumerate(profiles):
        for j, p_b in enumerate(profiles):
            if i >= j:
                continue

            score = 0.0
            reasons: List[str] = []

            id_a, id_b = p_a["id"], p_b["id"]

            # Rule 1: 状态联动 (A施压→B引爆，高价值)
            a_applies = pet_status_appliers.get(id_a, set())
            b_uses = pet_status_users.get(id_b, set())
            shared = a_applies & b_uses
            if shared:
                score += 30 * len(shared)
                reasons.append(f"{p_a['name']}施加{shared} -> {p_b['name']}利用")
            b_applies = pet_status_appliers.get(id_b, set())
            a_uses = pet_status_users.get(id_a, set())
            shared2 = b_applies & a_uses
            if shared2:
                score += 30 * len(shared2)
                reasons.append(f"{p_b['name']}施加{shared2} -> {p_a['name']}利用")

            # Rule 2: 天气联动
            wa = pet_weather_setters.get(id_a, "")
            wb = pet_weather_setters.get(id_b, "")
            if wa and pet_weather_types.get(id_b) == WEATHER_BENEFIT.get(wa):
                score += 25
                reasons.append(f"{p_a['name']}设{wa} -> {p_b['name']}受益")
            if wb and pet_weather_types.get(id_a) == WEATHER_BENEFIT.get(wb):
                score += 25
                reasons.append(f"{p_b['name']}设{wb} -> {p_a['name']}受益")

            # Rule 3: 抗性互补 (B能打A的弱点)
            a_weak = pet_weaknesses.get(id_a, set())
            b_cover = pet_coverages.get(id_b, set())
            complemented = a_weak & b_cover
            if complemented:
                score += 8 * len(complemented)
                reasons.append(f"{p_b['name']}覆盖{p_a['name']}的弱点{complemented}")

            # Rule 4: 标签重叠 (仅高价值标签)
            tags_a = pet_tags.get(id_a, set())
            tags_b = pet_tags.get(id_b, set())
            shared_tags = tags_a & tags_b
            high_value = {"灼烧", "中毒", "冻结", "星陨", "天气", "印记", "传动", "萌化", "寄生"}
            mid_value = {"增益传递", "先手", "连击", "吸血"}
            for tag in shared_tags & high_value:
                score += 6
            for tag in shared_tags & mid_value:
                score += 3

            # Rule 5: 应对链互补
            counter_tags = {"应对攻击", "应对防御", "应对状态"}
            a_counters = tags_a & counter_tags
            b_counters = tags_b & counter_tags
            if a_counters and b_counters and a_counters != b_counters:
                score += 12
                reasons.append(f"应对互补: {a_counters} <-> {b_counters}")

            # ══ 特性联动规则 (Ability-based) ══
            ab_a = pet_ability_tags.get(id_a, set())
            ab_b = pet_ability_tags.get(id_b, set())

            # Rule 6: 特性状态联动 — A特性含状态联动 + B能施加状态 = +20
            if "状态联动" in ab_a:
                b_statuses = set()
                for st in STATUS_SYNERGY:
                    if st in pet_status_appliers.get(id_b, set()):
                        b_statuses.add(st)
                if b_statuses:
                    score += 20 * len(b_statuses)
                    reasons.append(f"特性联动: {p_a['name']}特性状态联动 × {p_b['name']}施加{b_statuses}")
            if "状态联动" in ab_b:
                a_statuses = set()
                for st in STATUS_SYNERGY:
                    if st in pet_status_appliers.get(id_a, set()):
                        a_statuses.add(st)
                if a_statuses:
                    score += 20 * len(a_statuses)
                    reasons.append(f"特性联动: {p_b['name']}特性状态联动 × {p_a['name']}施加{a_statuses}")

            # Rule 7: 特性应对联动 — 双方特性都有应对增强 = +15
            if "应对增强" in ab_a and "应对增强" in ab_b:
                score += 15
                reasons.append(f"特性联动: 双方应对增强 ({p_a['name']} <-> {p_b['name']})")

            # Rule 8: 特性印记联动 — 双方特性都有印记联动 = +18
            if "印记联动" in ab_a and "印记联动" in ab_b:
                score += 18
                reasons.append(f"特性联动: 双方印记联动 ({p_a['name']} <-> {p_b['name']})")

            # Rule 9: 特性入场退场链 — A退场 + B入场 = +12
            if ("退场效果" in ab_a and "入场效果" in ab_b):
                score += 12
                reasons.append(f"特性联动: {p_a['name']}退场 × {p_b['name']}入场")
            if ("退场效果" in ab_b and "入场效果" in ab_a):
                score += 12
                reasons.append(f"特性联动: {p_b['name']}退场 × {p_a['name']}入场")

            # Rule 10: 特性蓄力迸发联动 — 双方特性都有蓄力联动 = +12
            if "蓄力联动" in ab_a and "蓄力联动" in ab_b:
                score += 12
                reasons.append(f"特性联动: 双方蓄力迸发 ({p_a['name']} <-> {p_b['name']})")

            # Rule 11: 特性天气联动 — A特性天气联动 + B能设天气 = +15
            if "天气联动" in ab_a and pet_weather_setters.get(id_b):
                score += 15
                reasons.append(f"特性联动: {p_a['name']}特性天气联动 × {p_b['name']}设{pet_weather_setters[id_b]}")
            if "天气联动" in ab_b and pet_weather_setters.get(id_a):
                score += 15
                reasons.append(f"特性联动: {p_b['name']}特性天气联动 × {p_a['name']}设{pet_weather_setters[id_a]}")

            # Rule 12: 特性能量循环 — A回能 + B降耗 = +15
            if "回能" in ab_a and "降耗" in ab_b:
                score += 15
                reasons.append(f"特性联动: {p_a['name']}回能 × {p_b['name']}降耗 (能量循环)")
            if "回能" in ab_b and "降耗" in ab_a:
                score += 15
                reasons.append(f"特性联动: {p_b['name']}回能 × {p_a['name']}降耗 (能量循环)")

            # Rule 13: 传动联动 — 双方都有传动联动标签 = +12
            if "传动联动" in ab_a and "传动联动" in ab_b:
                score += 12
                reasons.append(f"特性联动: 双方传动联动 ({p_a['name']} <-> {p_b['name']})")

            matrix[i][j] = score
            matrix[j][i] = score  # 对称

            if score >= 20:
                highlights.append({
                    "pet_a": p_a["name"],
                    "pet_b": p_b["name"],
                    "score": round(score, 1),
                    "reasons": reasons,
                })

    # ══ ML 融合 ══
    ml_matrix = None
    if pet_embeddings and ml_weight > 0:
        ml_matrix = compute_ml_synergy_matrix(profiles, pet_embeddings)
        # 加权融合
        matrix = matrix * (1.0 - ml_weight) + ml_matrix * ml_weight
        print(f"[synergy] ML 融合: ml_weight={ml_weight}, "
              f"max_rule={matrix.max():.0f} (pre-norm)")

    # 对称矩阵完成
    return matrix, highlights


def normalize_matrix(matrix: np.ndarray) -> np.ndarray:
    """将矩阵归一化到 0-100 范围。"""
    max_val = matrix.max()
    if max_val > 0:
        return (matrix / max_val) * 100.0
    return matrix


def main(ml_weight: float = 0.30):
    base = Path(__file__).resolve().parents[3]

    with open(base / "ml" / "data" / "pet_profiles.json", "r", encoding="utf-8") as f:
        profiles = json.load(f)
    with open(base / "scraper" / "output" / "type_chart.json", "r", encoding="utf-8") as f:
        type_chart = json.load(f)["chart"]

    # 尝试加载 pet embeddings（用于 ML 融合）
    pet_embeddings = None
    emb_path = base / "ml" / "data" / "pet_embeddings.npz"
    if emb_path.exists():
        pet_data = np.load(emb_path, allow_pickle=True)
        pet_embeddings = {
            int(pid): vec.astype(np.float32)
            for pid, vec in zip(pet_data["ids"], pet_data["vectors"])
        }
        print(f"加载 pet embeddings: {len(pet_embeddings)} 只")
    else:
        print("(无 embedding 文件，使用纯规则联动)")

    print(f"计算 {len(profiles)}×{len(profiles)} 联动矩阵...")
    matrix, highlights = compute_synergy_matrix(
        profiles, type_chart,
        pet_embeddings=pet_embeddings,
        ml_weight=ml_weight,
    )
    normalized = normalize_matrix(matrix)

    # 找出最高分的N对
    pairs = []
    n = len(profiles)
    for i in range(n):
        for j in range(i + 1, n):
            pairs.append((i, j, float(normalized[i][j])))
    pairs.sort(key=lambda x: -x[2])

    print(f"联动高分组合 Top 10:")
    for i, j, score in pairs[:10]:
        print(f"  {profiles[i]['name']} <-> {profiles[j]['name']}: {score:.1f}")

    # 稀疏存储: 只保留 top 10000 对
    top_pairs = []
    for i, j, score in pairs[:10000]:
        if score >= 1.0:
            top_pairs.append({
                "pet_a_id": profiles[i]["id"],
                "pet_a_name": profiles[i]["name"],
                "pet_b_id": profiles[j]["id"],
                "pet_b_name": profiles[j]["name"],
                "score": round(score, 1),
            })

    # 高联动原因
    top_highlights = sorted(highlights, key=lambda x: -x["score"])[:50]

    output = {
        "pet_count": n,
        "total_pairs": len(top_pairs),
        "pairs": top_pairs,
        "top_highlights": top_highlights,
        "ml_weight": ml_weight if pet_embeddings else 0.0,
    }
    out_path = base / "ml" / "data" / "synergy_graph.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 统计
    scores = [p["score"] for p in top_pairs]
    print(f"\n联动得分统计:")
    print(f"  有效对: {len(top_pairs)}")
    print(f"  最高分: {max(scores):.1f}")
    print(f"  平均分: {sum(scores)/len(scores):.1f}")
    print(f"  高分对(≥30): {sum(1 for s in scores if s >= 30)}")
    print(f"\n输出: {out_path}")


if __name__ == "__main__":
    main()

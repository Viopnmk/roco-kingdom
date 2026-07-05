"""
战术聚类 — 双重管道：规则引擎 + K-Means ML 聚类

规则管道 (baseline):
  基于预定义 TACTICAL_CLUSTERS 字典做标签匹配归类

ML 管道 (discovery):
  K-Means 在 384 维 embedding 空间自动发现战术模式
  - 自动 K 选择（silhouette score）
  - 命名簇（按主导标签/技能）
  - 与规则簇对比分析

输出: ml/data/tactical_clusters.json（含 ml_clusters + rule_clusters + 指标）
"""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from collections import defaultdict, Counter


# ══════════════════════════════════════════════════════════════════════
# 规则引擎 — 保留原有逻辑
# ══════════════════════════════════════════════════════════════════════

TACTICAL_CLUSTERS = {
    "灼烧体系": {
        "core_tags": ["灼烧"],
        "support_tags": ["能量操控", "减伤", "连击"],
        "description": "基于灼烧层数叠加+引爆的持续伤害体系",
    },
    "中毒消耗": {
        "core_tags": ["中毒"],
        "support_tags": ["减伤", "能量操控", "应对状态"],
        "description": "基于中毒层数的长期消耗战术",
    },
    "冻结控场": {
        "core_tags": ["冻结"],
        "support_tags": ["天气", "应对攻击", "先手"],
        "description": "暴风雪天气下冻结层数→力竭斩杀",
    },
    "星陨爆发": {
        "core_tags": ["星陨"],
        "support_tags": ["应对防御", "减伤", "连击"],
        "description": "叠星陨层数→一次性爆发的幻系伤害",
    },
    "萌化退化": {
        "core_tags": ["萌化"],
        "support_tags": ["减伤", "应对状态"],
        "description": "将对手退化到前一形态，降种族值",
    },
    "传动体系": {
        "core_tags": ["传动"],
        "support_tags": ["连击", "先手", "能量操控"],
        "description": "技能位移动+位置加成战术",
    },
    "天气队": {
        "core_tags": ["天气"],
        "support_tags": ["减伤", "应对攻击", "能量操控"],
        "description": "暴风雪/沙暴/雨天改变战场环境",
    },
    "应对返还": {
        "core_tags": ["应对攻击", "应对防御", "应对状态"],
        "support_tags": ["减伤", "能量操控", "先手"],
        "description": "三大应对机制为核心的反制战术",
    },
    "印记运营": {
        "core_tags": ["印记"],
        "support_tags": ["能量操控", "减伤"],
        "description": "通过印记系统获取持续优势",
    },
    "先手压制": {
        "core_tags": ["先手"],
        "support_tags": ["连击", "吸血", "巧变"],
        "description": "先手+1 + 高连击的快速压制流",
    },
    "吸血续航": {
        "core_tags": ["吸血"],
        "support_tags": ["连击", "减伤", "先手"],
        "description": "吸血+连击的永动续航",
    },
    "增益传递": {
        "core_tags": ["增益传递"],
        "support_tags": ["能量操控", "脱离"],
        "description": "增益继承+奉献的团队Buff传递",
    },
    "巧变切换": {
        "core_tags": ["巧变"],
        "support_tags": ["连击", "能量操控"],
        "description": "技能属性/类型切换的多面手",
    },
}


def cluster_by_tags(parsed_skills: List[dict]) -> Dict[str, List[str]]:
    """规则引擎：按标签将技能归类到预定义战术簇。"""
    clusters: Dict[str, List[str]] = defaultdict(list)
    for skill in parsed_skills:
        tags = set(skill.get("synergy_tags", []))
        if not tags:
            continue
        best_cluster = None
        best_score = 0
        for cluster_name, cluster_def in TACTICAL_CLUSTERS.items():
            core = set(cluster_def["core_tags"])
            support = set(cluster_def["support_tags"])
            score = len(tags & core) * 3 + len(tags & support) * 1
            if score > best_score:
                best_score = score
                best_cluster = cluster_name
        if best_cluster and best_score >= 1:
            clusters[best_cluster].append(skill["name"])
    return dict(clusters)


def cluster_pets_by_tactics(
    pet_profiles: List[dict],
    skill_clusters: Dict[str, List[str]],
) -> Dict[str, List[dict]]:
    """规则引擎：按战术簇归类精灵。"""
    skill_to_clusters: Dict[str, set] = defaultdict(set)
    for cluster_name, skill_names in skill_clusters.items():
        for sn in skill_names:
            skill_to_clusters[sn].add(cluster_name)

    pet_clusters: Dict[str, List[dict]] = defaultdict(list)
    for pet in pet_profiles:
        pet_tags = set(pet.get("synergy_tags", []))
        optimal = set(pet.get("optimal_skills", []))
        cluster_scores: Dict[str, int] = defaultdict(int)
        for skill_name in optimal:
            for cn in skill_to_clusters.get(skill_name, set()):
                cluster_scores[cn] += 1
        for cn, cdef in TACTICAL_CLUSTERS.items():
            cluster_scores[cn] += len(pet_tags & set(cdef["core_tags"])) * 2
        for cn, score in cluster_scores.items():
            if score >= 1:
                pet_clusters[cn].append({
                    "id": pet["id"],
                    "name": pet["name"],
                    "match_score": score,
                })
    for cn in pet_clusters:
        pet_clusters[cn].sort(key=lambda x: -x["match_score"])
    return dict(pet_clusters)


# ══════════════════════════════════════════════════════════════════════
# ML K-Means 聚类
# ══════════════════════════════════════════════════════════════════════

def cluster_skills_kmeans(
    skill_embeddings: Dict[str, np.ndarray],
    skill_tags: Dict[str, List[str]],
    n_clusters: Optional[int] = None,
    random_state: int = 42,
) -> Tuple[Dict[str, List[str]], np.ndarray, float, int]:
    """
    K-Means 在 embedding 空间聚类技能。

    Args:
        skill_embeddings: {技能名: 384维向量}
        skill_tags: {技能名: [标签列表]}  用于命名簇
        n_clusters: 指定 K 或 None（自动选择 K=8~20 使 silhouette 最大）

    Returns:
        (clusters_dict, cluster_centers, silhouette_score, n_clusters)
    """
    try:
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score
    except ImportError:
        print("[WARN] scikit-learn not installed. Using fallback K-Means (numpy).")
        return _fallback_kmeans(skill_embeddings, skill_tags, n_clusters)

    names = list(skill_embeddings.keys())
    X = np.stack([skill_embeddings[n] for n in names])

    if n_clusters is None:
        k_range = range(8, min(21, len(names)))
        best_k, best_score = 10, -1
        for k in k_range:
            km = KMeans(n_clusters=k, random_state=random_state, n_init=10, max_iter=300)
            labels = km.fit_predict(X)
            if len(set(labels)) < 2:
                continue
            score = silhouette_score(X, labels)
            if score > best_score:
                best_score = score
                best_k = k
        n_clusters = best_k
        print(f"[K-Means] 自动选择 K={n_clusters} (silhouette={best_score:.4f})")

    km = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10, max_iter=300)
    labels = km.fit_predict(X)
    final_silhouette = silhouette_score(X, labels)

    # 组织为 {簇标签: [技能名...]}
    clusters: Dict[str, List[str]] = defaultdict(list)
    for name, label in zip(names, labels):
        clusters[f"ml_{label:02d}"].append(name)

    # 命名 ML 簇
    named_clusters = _name_ml_clusters(clusters, skill_tags)

    print(f"[K-Means] {n_clusters} 个簇, silhouette={final_silhouette:.4f}")
    return named_clusters, km.cluster_centers_, final_silhouette, n_clusters


def _name_ml_clusters(
    clusters: Dict[str, List[str]],
    skill_tags: Dict[str, List[str]],
) -> Dict[str, List[str]]:
    """根据簇内高频标签为 ML 簇命名。"""
    named = {}
    for cluster_id, skill_names in sorted(clusters.items()):
        # 收集簇内所有标签
        all_tags: List[str] = []
        for sn in skill_names:
            all_tags.extend(skill_tags.get(sn, []))
        if not all_tags:
            named[f"{cluster_id}_未命名"] = skill_names
            continue
        counter = Counter(all_tags)
        top3 = [tag for tag, _ in counter.most_common(3)]
        cluster_name = f"{cluster_id}_{'·'.join(top3)}"
        named[cluster_name] = skill_names
    return named


def _fallback_kmeans(
    skill_embeddings: Dict[str, np.ndarray],
    skill_tags: Dict[str, List[str]],
    n_clusters: Optional[int] = None,
) -> Tuple[Dict[str, List[str]], np.ndarray, float, int]:
    """纯 numpy K-Means 备选（不依赖 sklearn）。"""
    names = list(skill_embeddings.keys())
    X = np.stack([skill_embeddings[n] for n in names])
    k = n_clusters or 12

    # 随机初始化中心
    rng = np.random.RandomState(42)
    indices = rng.choice(len(X), k, replace=False)
    centers = X[indices].copy()

    for _ in range(50):
        # 分配
        dots = X @ centers.T  # cosine similarity
        labels = np.argmax(dots, axis=1)  # nearest center
        # 更新中心
        new_centers = np.zeros_like(centers)
        for j in range(k):
            mask = labels == j
            if mask.any():
                new_centers[j] = X[mask].mean(axis=0)
                new_centers[j] /= np.linalg.norm(new_centers[j]) or 1
        if np.allclose(centers, new_centers):
            break
        centers = new_centers

    clusters: Dict[str, List[str]] = defaultdict(list)
    for name, label in zip(names, labels):
        clusters[f"ml_{label:02d}"].append(name)

    named = _name_ml_clusters(clusters, skill_tags)
    # Approximate silhouette
    approx_silhouette = _approximate_silhouette(X, labels)
    print(f"[fallback K-Means] {k} clusters, approx silhouette={approx_silhouette:.4f}")
    return named, centers, approx_silhouette, k


def _approximate_silhouette(X: np.ndarray, labels: np.ndarray, sample: int = 500) -> float:
    """近似 silhouette score（余弦距离）。"""
    n = len(X)
    indices = np.random.RandomState(42).choice(n, min(sample, n), replace=False)
    scores = []
    for i in indices:
        same_cluster = X[labels == labels[i]]
        if len(same_cluster) <= 1:
            continue
        a = 1 - (X[i] @ same_cluster.T).mean()  # cosine distance within cluster
        b_vals = []
        for l in set(labels) - {labels[i]}:
            other = X[labels == l]
            b_vals.append(1 - (X[i] @ other.T).mean())
        b = min(b_vals) if b_vals else a
        scores.append((b - a) / max(a, b) if max(a, b) > 0 else 0)
    return float(np.mean(scores)) if scores else 0.0


# ══════════════════════════════════════════════════════════════════════
# 簇评估 & 对比
# ══════════════════════════════════════════════════════════════════════

def compare_clusters(
    rule_clusters: Dict[str, List[str]],
    ml_clusters: Dict[str, List[str]],
) -> dict:
    """
    对比规则簇与 ML 簇的重叠度。

    Returns:
        {rule_cluster: [{ml_cluster: overlap_rate}]}
    """
    comparison = {}
    for rule_name, rule_skills in rule_clusters.items():
        rule_set = set(rule_skills)
        overlaps = {}
        for ml_name, ml_skills in ml_clusters.items():
            ml_set = set(ml_skills)
            intersection = rule_set & ml_set
            if intersection:
                jaccard = len(intersection) / len(rule_set | ml_set)
                overlaps[ml_name] = {
                    "shared": len(intersection),
                    "jaccard": round(jaccard, 3),
                }
        if overlaps:
            comparison[rule_name] = dict(
                sorted(overlaps.items(), key=lambda x: -x[1]["jaccard"])
            )
    return comparison


def print_cluster_summary(
    rule_clusters: Dict[str, List[str]],
    ml_clusters: Dict[str, List[str]],
    comparison: dict,
) -> None:
    """打印聚类摘要。"""
    print("\n" + "=" * 60)
    print("规则簇 (Rule-based)")
    print("=" * 60)
    for cn, snames in sorted(rule_clusters.items(), key=lambda x: -len(x[1])):
        print(f"  {cn:10s}: {len(snames):3d} 技能  {snames[:5]}...")

    print("\n" + "=" * 60)
    print("ML 簇 (K-Means)")
    print("=" * 60)
    for cn, snames in sorted(ml_clusters.items(), key=lambda x: -len(x[1])):
        print(f"  {cn}: {len(snames):3d} 技能  {snames[:5]}...")

    print("\n" + "=" * 60)
    print("规则 <-> ML 重叠 (Top 3 per rule cluster)")
    print("=" * 60)
    for rule_name, overlaps in sorted(comparison.items()):
        top = list(overlaps.items())[:3]
        items = [f"{ml_name}(J={info['jaccard']:.2f})" for ml_name, info in top]
        print(f"  {rule_name:10s} → {', '.join(items)}")


# ══════════════════════════════════════════════════════════════════════
# 主入口
# ══════════════════════════════════════════════════════════════════════

def run_clustering(
    parsed_skills: List[dict],
    pet_profiles: List[dict],
    skill_embeddings: Optional[Dict[str, np.ndarray]] = None,
) -> dict:
    """
    完整聚类流程：规则 + ML 双管道。

    Returns:
        聚类结果字典（用于保存）
    """
    # 规则管道
    rule_skill_clusters = cluster_by_tags(parsed_skills)
    rule_pet_clusters = cluster_pets_by_tactics(pet_profiles, rule_skill_clusters)

    # ML 管道
    skill_tags = {s["name"]: s.get("synergy_tags", []) for s in parsed_skills}
    if skill_embeddings and len(skill_embeddings) > 0:
        emb_dim = next(iter(skill_embeddings.values())).shape[0]
        # 只用 embedding 维度 > 1 的真实 embedding（排除 fallback 标签向量）
        if emb_dim > 50:
            ml_skill_clusters, centers, silhouette, n_clusters = cluster_skills_kmeans(
                skill_embeddings, skill_tags, n_clusters=None
            )
            comparison = compare_clusters(rule_skill_clusters, ml_skill_clusters)
            print_cluster_summary(rule_skill_clusters, ml_skill_clusters, comparison)
        else:
            print("[cluster] 检测到标签向量（非 NLP embedding），跳过 ML 聚类")
            ml_skill_clusters = {}
            centers = np.array([])
            silhouette = 0.0
            n_clusters = 0
            comparison = {}
    else:
        print("[cluster] 无 embedding 数据，仅运行规则聚类")
        ml_skill_clusters = {}
        centers = np.array([])
        silhouette = 0.0
        n_clusters = 0
        comparison = {}

    # 组装输出
    return {
        "rule_clusters": {
            "skills": rule_skill_clusters,
            "pets": rule_pet_clusters,
            "definitions": TACTICAL_CLUSTERS,
        },
        "ml_clusters": {
            "skills": ml_skill_clusters,
            "n_clusters": n_clusters,
            "silhouette_score": round(silhouette, 4),
            "method": "K-Means on NLP embeddings",
        },
        "cluster_comparison": comparison,
    }


def main():
    base = Path(__file__).resolve().parents[3]

    with open(base / "ml" / "data" / "parsed_skills.json", "r", encoding="utf-8") as f:
        skills = json.load(f)
    with open(base / "ml" / "data" / "pet_profiles.json", "r", encoding="utf-8") as f:
        pets = json.load(f)

    # 尝试加载 embedding
    from embed import load_embeddings
    skill_emb, pet_emb = load_embeddings(base / "ml" / "data")

    result = run_clustering(skills, pets, skill_emb if skill_emb else None)

    out_path = base / "ml" / "data" / "tactical_clusters.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n输出: {out_path}")


if __name__ == "__main__":
    main()

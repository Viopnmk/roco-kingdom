"""
多轮训练管道 — 串联 Embedding → Clustering → Synergy 全流程

每次运行算一轮，记录元数据用于跨轮对比：
  - 技能/精灵数量变化
  - 聚类 metrics (silhouette / K / 簇分布)
  - ML 联动覆盖范围

用法:
    python -m src.train              # 运行新轮次
    python -m src.train --force      # 强制重新计算 embedding（忽略缓存）
    python -m src.train --round 1    # 指定轮次编号
"""

import json
import sys
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Dict

# 确保 ml/ 在 sys.path 上
_ml_dir = Path(__file__).resolve().parents[1]  # 洛克王国/ml/
if str(_ml_dir) not in sys.path:
    sys.path.insert(0, str(_ml_dir))

# 项目根目录
_project_root = Path(__file__).resolve().parents[2]  # 洛克王国/

from src.discovery.embed import run_embedding
from src.discovery.cluster import run_clustering
from src.discovery.graph import compute_synergy_matrix, normalize_matrix


def _tz() -> timezone:
    """东八区。"""
    return timezone(timedelta(hours=8))


def load_data(base: Path):
    """加载全部源数据。"""
    with open(base / "scraper" / "output" / "pets.json", "r", encoding="utf-8") as f:
        pets = json.load(f)
    with open(base / "ml" / "data" / "parsed_skills.json", "r", encoding="utf-8") as f:
        parsed_skills = json.load(f)
    with open(base / "ml" / "data" / "pet_profiles.json", "r", encoding="utf-8") as f:
        pet_profiles = json.load(f)
    with open(base / "scraper" / "output" / "type_chart.json", "r", encoding="utf-8") as f:
        type_chart = json.load(f)["chart"]
    return pets, parsed_skills, pet_profiles, type_chart


def load_train_meta(base: Path) -> dict:
    """加载训练元数据（存在则返回，否则空）。"""
    path = base / "ml" / "data" / "train_meta.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"rounds": [], "current_round": 0}


def save_train_meta(base: Path, meta: dict) -> None:
    """保存训练元数据。"""
    path = base / "ml" / "data" / "train_meta.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"元数据保存: {path}")


def print_comparison(meta: dict) -> None:
    """打印多轮指标对比表。"""
    rounds = meta.get("rounds", [])
    if len(rounds) < 2:
        return

    print("\n" + "=" * 70)
    print("多轮指标对比")
    print("=" * 70)
    header = f"{'Round':>5}  {'日期':12s}  {'技能':>4}  {'精灵':>4}  {'K':>3}  {'Silhouette':>10}  {'ML联动':>7}"
    print(header)
    print("-" * 70)
    for r in rounds:
        metrics = r.get("metrics", {})
        ml = metrics.get("ml_clusters", {})
        synergy = metrics.get("synergy", {})
        print(
            f"{r['round']:>5}  {r['timestamp'][:10]:12s}  "
            f"{r['skill_count']:>4}  {r['pet_count']:>4}  "
            f"{ml.get('n_clusters', '-'):>3}  "
            f"{ml.get('silhouette_score', '-'):>10}  "
            f"{'yes' if synergy.get('ml_weight', 0) > 0 else 'no':>7}"
        )
    print()

    # 变化检测
    if len(rounds) >= 2:
        curr = rounds[-1]
        prev = rounds[-2]
        skill_delta = curr["skill_count"] - prev["skill_count"]
        pet_delta = curr["pet_count"] - prev["pet_count"]
        sil_curr = curr.get("metrics", {}).get("ml_clusters", {}).get("silhouette_score", 0)
        sil_prev = prev.get("metrics", {}).get("ml_clusters", {}).get("silhouette_score", 0)
        print(f"变化: 技能 {skill_delta:+d}  精灵 {pet_delta:+d}  "
              f"Silhouette {sil_prev:.4f} → {sil_curr:.4f} ({sil_curr - sil_prev:+.4f})")


def run(force_reembed: bool = False, round_num: int = None, ml_weight: float = 0.30):
    """
    执行一轮完整训练管道。
    """
    base = _project_root
    assert (base / "ml" / "data").exists(), f"项目根检测失败: {base}"

    t_start = time.time()

    # ── 加载数据 ──
    print("=" * 60)
    print("洛克王国 AI 配队 — 训练管道")
    print("=" * 60)
    pets, parsed_skills, pet_profiles, type_chart = load_data(base)

    # ── 元数据 ──
    meta = load_train_meta(base)
    if round_num is None:
        round_num = meta["current_round"] + 1
    print(f"\n[Round {round_num}] 开始 — {datetime.now(_tz()).isoformat(timespec='seconds')}")
    print(f"  技能: {len(parsed_skills)}  精灵: {len(pets)}  精灵画像: {len(pet_profiles)}")

    # ── Step 1: Embedding ──
    print("\n── Step 1: NLP Embedding ──")
    skill_emb, pet_emb = run_embedding(
        parsed_skills, pet_profiles,
        force=force_reembed,
    )

    # ── Step 2: Clustering ──
    print("\n── Step 2: 战术聚类 ──")
    cluster_result = run_clustering(parsed_skills, pet_profiles, skill_emb)

    # ── Step 3: Synergy ──
    print("\n── Step 3: 联动矩阵 ──")

    use_ml = len(pet_emb) > 0
    emb_dim = next(iter(pet_emb.values())).shape[0] if use_ml else 0
    actual_ml_weight = ml_weight if (use_ml and emb_dim > 50) else 0.0

    matrix, highlights = compute_synergy_matrix(
        pet_profiles, type_chart,
        pet_embeddings=pet_emb if actual_ml_weight > 0 else None,
        ml_weight=actual_ml_weight,
    )
    normalized = normalize_matrix(matrix)

    # 提取 Top pairs
    n = len(pet_profiles)
    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            pairs.append((i, j, float(normalized[i][j])))
    pairs.sort(key=lambda x: -x[2])

    top_pairs = []
    for i, j, score in pairs[:10000]:
        if score >= 1.0:
            top_pairs.append({
                "pet_a_id": pet_profiles[i]["id"],
                "pet_a_name": pet_profiles[i]["name"],
                "pet_b_id": pet_profiles[j]["id"],
                "pet_b_name": pet_profiles[j]["name"],
                "score": round(score, 1),
            })

    top_highlights = sorted(highlights, key=lambda x: -x["score"])[:50]

    synergy_output = {
        "pet_count": n,
        "total_pairs": len(top_pairs),
        "pairs": top_pairs,
        "top_highlights": top_highlights,
        "ml_weight": actual_ml_weight,
    }
    with open(base / "ml" / "data" / "synergy_graph.json", "w", encoding="utf-8") as f:
        json.dump(synergy_output, f, ensure_ascii=False, indent=2)

    # 统计
    scores = [p["score"] for p in top_pairs]
    print(f"  有效联动对: {len(top_pairs)}")
    print(f"  最高分: {max(scores):.1f}  平均分: {sum(scores)/len(scores):.1f}")
    print(f"  高分对(≥30): {sum(1 for s in scores if s >= 30)}")

    # ── Step 4: 记录元数据 ──
    round_metrics = {
        "ml_clusters": cluster_result.get("ml_clusters", {}),
        "synergy": {
            "total_pairs": len(top_pairs),
            "max_score": float(max(scores)),
            "mean_score": float(sum(scores) / len(scores)),
            "high_score_pairs": int(sum(1 for s in scores if s >= 30)),
            "ml_weight": actual_ml_weight,
        },
    }

    round_entry = {
        "round": round_num,
        "timestamp": datetime.now(_tz()).isoformat(timespec="seconds"),
        "skill_count": len(parsed_skills),
        "pet_count": len(pets),
        "model": "paraphrase-multilingual-MiniLM-L12-v2",
        "emb_dim": emb_dim if emb_dim > 0 else None,
        "metrics": round_metrics,
        "elapsed_seconds": round(time.time() - t_start, 1),
    }
    meta["rounds"].append(round_entry)
    meta["current_round"] = round_num
    save_train_meta(base, meta)

    # ── 跨轮对比 ──
    print_comparison(meta)

    print(f"\n[Round {round_num}] 完成 — 耗时 {time.time() - t_start:.1f}s")


# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="多轮训练管道")
    parser.add_argument("--force", action="store_true", help="强制重新计算 embedding")
    parser.add_argument("--round", type=int, help="指定轮次编号")
    parser.add_argument("--ml-weight", type=float, default=0.30, help="ML 联动权重 (0-1)")
    args = parser.parse_args()
    run(force_reembed=args.force, round_num=args.round, ml_weight=args.ml_weight)

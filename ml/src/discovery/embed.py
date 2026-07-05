"""
技能效果文本向量化 — 使用 MiniLM 本地模型

输入: parsed_skills.json
输出: 494技能 × 384维向量 (归一化)
"""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple


def embed_skills(skills: List[dict], model_name: str = "paraphrase-multilingual-MiniLM-L12-v2") -> Dict[str, np.ndarray]:
    """
    对技能效果文本做 embedding，返回 {技能名: 384维向量}。

    网络不可用时自动降级到标签向量（24维 one-hot）。
    HF 镜像通过环境变量 HF_ENDPOINT=https://hf-mirror.com 设置。
    """
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("[WARN] sentence-transformers 未安装。使用标签向量替代。")
        print("       安装: pip install sentence-transformers")
        return _fallback_tag_vectors(skills)

    print(f"加载模型: {model_name} ...")
    try:
        model = SentenceTransformer(model_name, device="cpu")
    except (OSError, ConnectionError, Exception) as e:
        print(f"[WARN] 模型加载失败: {e}")
        print("[WARN] 可能是网络不通（HuggingFace 被墙）。使用标签向量替代。")
        print("       设置镜像: set HF_ENDPOINT=https://hf-mirror.com")
        return _fallback_tag_vectors(skills)

    print(f"模型已加载，维度: {model.get_sentence_embedding_dimension()}")

    # 提取所有效果文本
    texts = [s.get("effect_raw", s.get("effect", "")) or "无效果" for s in skills]
    names = [s["name"] for s in skills]

    print(f"编码 {len(texts)} 个技能文本...")
    embeddings = model.encode(texts, show_progress_bar=True, normalize_embeddings=True)

    result = {name: emb for name, emb in zip(names, embeddings)}
    print(f"完成: {len(result)} 个向量")
    return result


def _fallback_tag_vectors(skills: List[dict]) -> Dict[str, np.ndarray]:
    """
    备选方案：用标签 one-hot 向量替代 NLP embedding。
    24维向量（每个标签一位），归一化。
    """
    ALL_TAGS = [
        "灼烧", "中毒", "冻结", "星陨", "萌化", "寄生",
        "应对攻击", "应对防御", "应对状态", "先手", "蓄力", "传动", "脱离",
        "连击", "吸血", "减伤", "天气", "印记", "迅捷", "折返", "迸发", "巧变",
        "能量操控", "增益传递", "打断",
    ]
    tag_to_idx = {t: i for i, t in enumerate(ALL_TAGS)}
    dim = len(ALL_TAGS)
    result = {}
    for s in skills:
        vec = np.zeros(dim, dtype=np.float32)
        for tag in s.get("synergy_tags", []):
            if tag in tag_to_idx:
                vec[tag_to_idx[tag]] = 1.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        result[s["name"]] = vec
    print(f"使用标签向量: {dim}维, {len(result)} 个技能")
    return result


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """已归一化向量的余弦相似度 = 点积。"""
    return float(np.dot(a, b))


def find_similar_skills(name: str, embeddings: Dict[str, np.ndarray], top_k: int = 10) -> List[tuple]:
    """根据 embedding 找最相似的技能。"""
    if name not in embeddings:
        return []
    vec = embeddings[name]
    scores = []
    for other_name, other_vec in embeddings.items():
        if other_name == name:
            continue
        scores.append((other_name, cosine_similarity(vec, other_vec)))
    scores.sort(key=lambda x: -x[1])
    return scores[:top_k]


# ── 精灵级 Embedding ────────────────────────────────────────────────

def embed_pets(
    pet_profiles: List[dict],
    skill_embeddings: Dict[str, np.ndarray],
) -> Dict[int, np.ndarray]:
    """
    计算精灵向量 = 其最优 4 技能 embedding 的均值（重新归一化）。

    无最优技能的精灵返回零向量（保留占位）。
    """
    result: Dict[int, np.ndarray] = {}
    missing = 0
    for pet in pet_profiles:
        pid = pet["id"]
        skills = pet.get("optimal_skills", [])
        vecs = []
        for sname in skills:
            if sname in skill_embeddings:
                vecs.append(skill_embeddings[sname])
        if vecs:
            avg = np.mean(vecs, axis=0)
            norm = np.linalg.norm(avg)
            if norm > 0:
                avg /= norm
            result[pid] = avg
        else:
            result[pid] = np.zeros(384, dtype=np.float32)
            missing += 1
    print(f"精灵 embedding: {len(result)} 只 (无技能数据: {missing})")
    return result


# ── 持久化 ──────────────────────────────────────────────────────────

def save_embeddings(
    skill_embeddings: Dict[str, np.ndarray],
    pet_embeddings: Dict[int, np.ndarray],
    output_dir: Path,
) -> None:
    """保存技能和精灵 embedding 到压缩 .npz 文件。"""
    output_dir.mkdir(parents=True, exist_ok=True)

    skill_names = list(skill_embeddings.keys())
    skill_matrix = np.stack([skill_embeddings[n] for n in skill_names])
    np.savez_compressed(
        output_dir / "skill_embeddings.npz",
        names=np.array(skill_names, dtype=object),
        vectors=skill_matrix,
    )

    pet_ids = sorted(pet_embeddings.keys())
    pet_matrix = np.stack([pet_embeddings[pid] for pid in pet_ids])
    np.savez_compressed(
        output_dir / "pet_embeddings.npz",
        ids=np.array(pet_ids, dtype=np.int32),
        vectors=pet_matrix,
    )

    dim = skill_matrix.shape[1]
    print(f"保存完成: {len(skill_names)} skills × {dim}d, "
          f"{len(pet_ids)} pets × {dim}d → {output_dir}")


def load_embeddings(data_dir: Path) -> Tuple[Dict[str, np.ndarray], Dict[int, np.ndarray]]:
    """加载已保存的 embedding。文件不存在则返回空字典。"""
    skill_file = data_dir / "skill_embeddings.npz"
    pet_file = data_dir / "pet_embeddings.npz"

    if not skill_file.exists() or not pet_file.exists():
        return {}, {}

    skill_data = np.load(skill_file, allow_pickle=True)
    skill_embeddings = {
        name: vec.astype(np.float32)
        for name, vec in zip(skill_data["names"], skill_data["vectors"])
    }

    pet_data = np.load(pet_file, allow_pickle=True)
    pet_embeddings = {
        int(pid): vec.astype(np.float32)
        for pid, vec in zip(pet_data["ids"], pet_data["vectors"])
    }

    return skill_embeddings, pet_embeddings


def run_embedding(
    parsed_skills: List[dict],
    pet_profiles: List[dict],
    model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
    force: bool = False,
) -> Tuple[Dict[str, np.ndarray], Dict[int, np.ndarray]]:
    """
    完整 embedding 流程：加载/计算技能向量 → 聚合精灵向量。

    Args:
        force: 强制重新计算，忽略缓存
    """
    base = Path(__file__).resolve().parents[3]
    data_dir = base / "ml" / "data"

    if not force:
        skill_emb, pet_emb = load_embeddings(data_dir)
        if skill_emb and pet_emb:
            print(f"[embed] 使用缓存: {len(skill_emb)} skills, {len(pet_emb)} pets")
            return skill_emb, pet_emb

    skill_emb = embed_skills(parsed_skills, model_name)
    pet_emb = embed_pets(pet_profiles, skill_emb)
    save_embeddings(skill_emb, pet_emb, data_dir)

    # 相似技能示例（质量抽查）
    demo_target = "充分燃烧"
    similar = find_similar_skills(demo_target, skill_emb, 5)
    print(f"\n[embed] 与「{demo_target}」最相似的 5 个技能:")
    for sname, score in similar:
        print(f"  {sname}: {score:.3f}")

    return skill_emb, pet_emb


if __name__ == "__main__":
    base = Path(__file__).resolve().parents[3]
    skills_path = base / "ml" / "data" / "parsed_skills.json"
    with open(skills_path, "r", encoding="utf-8") as f:
        skills = json.load(f)

    embs = embed_skills(skills)

    # 测试: 找和"充分燃烧"最相似的技能
    similar = find_similar_skills("充分燃烧", embs, 5)
    print(f"\n与「充分燃烧」最相似的技能:")
    for name, score in similar:
        print(f"  {name}: {score:.3f}")

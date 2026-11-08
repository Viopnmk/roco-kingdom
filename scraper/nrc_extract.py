#!/usr/bin/env python
"""
nrc BWIKI（wiki.biligame.com/nrc）数据提取 —— 2026-11-08 为 S5 更新新建。

旧站 wiki.biligame.com/rocom 已冻结（最近编辑 2026-09-24），勿用。
nrc 的数据结构：
  - legacy 数据在 Lua 模块 Module:Pets/data/{Catalog,Skills,Learnsets,
    Evolutions,Handbooks,Index,Overview} 与 Module:Pets/EvolutionConditions；
  - 当前赛季（S5）数据在 Module:精灵图鉴/S5/数据/{精灵,技能,特性,关联,辅助}，
    使用 "dragon-tuples-1" 字典编码（解码规则见 Module:精灵图鉴/S5 的
    unpackShard）；赛季视图 = legacy 逐 key 被赛季分片覆盖/追加，
    本脚本按同一规则合并（Roster->Catalog、Arts+Gifts->Skills、
    Aux->{Learnsets,Evolutions,Handbooks,Index,Overview,...}、
    另有 SeasonLearnsets 给旧精灵追加 S5 技能石）。
  - Module:ContentVisibility/S5Legacy/* 是「旧版视图」专用补丁，
    当前站点配置（hidden_seasons.S5=false）下不生效，本脚本不应用。

产物与 web/src/data 现有 schema 完全一致：
  pets.json / skills.json / learnset.json / evolution_chains.json /
  stats.json / candidate_ids.ts

用法：~/workspace/roco-kingdom/.venv/bin/python scraper/nrc_extract.py
原始模块缓存到 scraper/data/nrc_raw/，diff 摘要打印到 stdout。
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nrc_luaparse import parse_lua  # noqa: E402

API = "https://wiki.biligame.com/nrc/api.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Referer": "https://wiki.biligame.com/nrc/",
}
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(BASE_DIR, "data", "nrc_raw")
WEB_DATA = os.path.join(BASE_DIR, "..", "web", "src", "data")

LEGACY_MODULES = [
    "模块:Pets/data/Catalog", "模块:Pets/data/Skills", "模块:Pets/data/Learnsets",
    "模块:Pets/data/Evolutions", "模块:Pets/data/Handbooks", "模块:Pets/data/Index",
    "模块:Pets/data/Overview", "模块:Pets/EvolutionConditions",
]
S5_SHARDS = [
    "模块:精灵图鉴/S5/数据/精灵", "模块:精灵图鉴/S5/数据/技能",
    "模块:精灵图鉴/S5/数据/特性", "模块:精灵图鉴/S5/数据/关联",
    "模块:精灵图鉴/S5/数据/辅助",
]

_session = requests.Session()
_session.headers.update(HEADERS)


def fetch_wikitext(title: str) -> str:
    r = _session.get(API, params={
        "action": "query", "prop": "revisions", "rvprop": "content",
        "rvslots": "main", "titles": title, "format": "json",
    }, timeout=120)
    r.raise_for_status()
    for page in r.json()["query"]["pages"].values():
        if "revisions" in page:
            return page["revisions"][0]["slots"]["main"]["*"]
    raise RuntimeError(f"page missing: {title}")


def load_module(title: str):
    """取模块源码（带本地缓存）并解析 Lua 数据表。"""
    os.makedirs(RAW_DIR, exist_ok=True)
    cache = os.path.join(RAW_DIR, title.replace(":", "_").replace("/", "_") + ".txt")
    if os.path.exists(cache):
        text = open(cache, encoding="utf-8").read()
    else:
        text = fetch_wikitext(title)
        open(cache, "w", encoding="utf-8").write(text)
    return parse_lua(text)


def decode_shard(packed):
    """dragon-tuples-1 解码（与 Module:精灵图鉴/S5 unpackShard 等价）。"""
    assert packed[0] == "dragon-tuples-1", packed[0]
    fields = packed[1]

    def dec(v):
        if isinstance(v, list):
            if not v:
                return {}
            if v[0] == 1:
                return {fields[e[0] - 1]: dec(e[1]) for e in v[1]}
            if v[0] == 2:
                return [dec(c) for c in v[1]]
            raise ValueError(f"bad node tag {v[0]}")
        return v

    return dec(packed[2])


# ---------------------------------------------------------------- 合并
def merged_data():
    legacy = {}
    for t in LEGACY_MODULES:
        legacy[t.split("/")[-1]] = load_module(t)
    shards = {}
    for t in S5_SHARDS:
        shards[t.split("/")[-1]] = decode_shard(load_module(t))

    catalog = dict(legacy["Catalog"])
    catalog.update(shards["精灵"])                      # Roster
    skills = dict(legacy["Skills"])
    skills.update(shards["技能"])                      # Arts
    skills.update(shards["特性"])                      # Gifts
    learnsets = dict(legacy["Learnsets"])
    evolutions = dict(legacy["Evolutions"])
    handbooks = dict(legacy["Handbooks"])
    overview = dict(legacy["Overview"])
    aux = shards["辅助"]
    learnsets.update(aux.get("Learnsets") or {})
    evolutions.update(aux.get("Evolutions") or {})
    handbooks.update(aux.get("Handbooks") or {})
    overview.update(aux.get("Overview") or {})
    # 进化别名：S5 视图中旧 key 指向新 entry（同 Module:Pets/SeasonData 逻辑）
    for old, new in (aux.get("LegacyEvolutionAliases") or {}).items():
        if new in evolutions:
            evolutions[old] = evolutions[new]
    season_stones = aux.get("SeasonLearnsets") or {}   # {pet_id: {skill_stones:[...]}}
    targets = (shards["关联"] or {}).get("Targets") or {}
    return {
        "catalog": catalog, "skills": skills, "learnsets": learnsets,
        "evolutions": evolutions, "handbooks": handbooks, "overview": overview,
        "evo_conditions": legacy["EvolutionConditions"],
        "season_stones": season_stones, "targets_pet": targets.get("pet") or {},
    }


# ---------------------------------------------------------------- 工具
TYPE_MAP = {"幽": "幽灵"}

def type_name(element: str) -> str:
    t = (element or "").removesuffix("系")
    return TYPE_MAP.get(t, t)

def display_name(title: str) -> str:
    return title.replace("（", "").replace("）", "").replace("(", "").replace(")", "")

def stat_total(st) -> int:
    return st["hp"] + st["atk"] + st["def"] + st["spa"] + st["spd"] + st["spe"]


# ---------------------------------------------------------------- 主流程
def main():
    data = merged_data()
    catalog, skills = data["catalog"], data["skills"]
    learnsets, handbooks = data["learnsets"], data["handbooks"]
    overview = data["overview"]

    baseline_pets = json.load(open(os.path.join(WEB_DATA, "pets.json"), encoding="utf-8"))
    baseline_by_name = {p["name"]: p for p in baseline_pets}
    used_ids = {p["id"] for p in baseline_pets}

    # ---- 显示名（标题去括号），冲突时回退到带括号标题
    title_of = {}
    for pid, row in catalog.items():
        title_of[pid] = data["targets_pet"].get(pid) or row.get("title") or row["name"]
    name_count = Counter(display_name(t) for t in title_of.values())
    disp = {}
    for pid, t in title_of.items():
        dn = display_name(t)
        disp[pid] = dn if name_count[dn] == 1 else t

    # ---- ID 分配：同名沿用基线 ID，新精灵从 592 起顺延
    new_pids = [pid for pid in catalog if disp[pid] not in baseline_by_name]
    new_pids.sort(key=lambda p: (int(catalog[p]["number"]), title_of[p]))
    next_id = 592
    pid_to_id = {}
    for pid, row in catalog.items():
        if disp[pid] in baseline_by_name:
            pid_to_id[pid] = baseline_by_name[disp[pid]]["id"]
    for pid in new_pids:
        while next_id in used_ids:
            next_id += 1
        pid_to_id[pid] = next_id
        used_ids.add(next_id)
        next_id += 1

    skill_name = {sid: (row.get("name") or sid) for sid, row in skills.items()}

    # ---- 学习面（按 learnset_id 查表 + SeasonLearnsets 追加技能石）
    def pet_learnset(pid):
        row = catalog[pid]
        ls = learnsets.get(row.get("learnset_id") or "", {})
        native = [e["skill"] for e in ls.get("native_skills") or []]
        stones = list(ls.get("skill_stones") or [])
        blood = [e["skill"] for e in ls.get("blood_skills") or []]
        extra = (data["season_stones"].get(pid) or {}).get("skill_stones") or []
        for s in extra:
            if s not in stones:
                stones.append(s)
        return native, stones, blood

    # ---- 特殊进化条件（按页面标题）
    evo_cond = data["evo_conditions"] or {}

    pets_out = []
    learnset_out = []
    seen_ls = set()
    for pid, row in catalog.items():
        st = row["stats"]
        types = [type_name(t) for t in row.get("types") or []]
        native, stones, blood = pet_learnset(pid)
        ability = skill_name.get(row.get("feature_skill_id") or "", "")
        hb = handbooks.get(row.get("handbook_id") or "", {})
        pet = {
            "id": pid_to_id[pid],
            "name": disp[pid],
            "type_primary": types[0] if types else "",
            "stats": {
                "hp": st["hp"], "atk": st["atk"], "defense": st["def"],
                "sp_atk": st["spa"], "sp_def": st["spd"], "speed": st["spe"],
                "total": stat_total(st),
            },
            "ability": ability,
            "height": (row.get("height") or "").removesuffix("M"),
            "weight": (row.get("weight") or "").removesuffix("KG"),
            "description": row.get("description") or "",
            "evolution_chain": [],
            "how_to_get": hb.get("habitat") or "",
            "skills": [skill_name.get(s, s) for s in native],
            "stone_skills": [skill_name.get(s, s) for s in stones],
            "bloodline_skills": [skill_name.get(s, s) for s in blood],
            "source": "bwiki-nrc",
        }
        if len(types) > 1:
            pet["type_secondary"] = types[1]
        # 特殊进化条件（基线 evolution_chain 字段的既有语义：特殊条件注记）
        conds = evo_cond.get(title_of[pid]) or {}
        for _target, cond in conds.items():
            m = re.search(r"(\d+)\s*级", cond or "")
            pet["evolution_chain"].append({
                "name": cond, "level": int(m.group(1)) if m else None,
            })
        pets_out.append(pet)
        for src, lst in (("level", native), ("stone", stones), ("bloodline", blood)):
            for s in lst:
                key = (pet["id"], skill_name.get(s, s), src)
                if key not in seen_ls:
                    seen_ls.add(key)
                    learnset_out.append({
                        "pet_id": pet["id"], "pet_name": pet["name"],
                        "skill_name": skill_name.get(s, s), "source": src,
                    })
    pets_out.sort(key=lambda p: p["id"])
    learnset_out.sort(key=lambda e: (e["pet_id"], e["source"], e["skill_name"]))
    pet_by_id = {p["id"]: p for p in pets_out}

    # ---- 技能表：仅收录被学习面引用的非特性技能（与基线口径一致）
    ref_skill_ids = set()
    for pid in catalog:
        n, s, b = pet_learnset(pid)
        ref_skill_ids.update(n + s + b)
    skills_out = []
    for sid in sorted(ref_skill_ids, key=lambda s: (skills[s].get("game_id") or 0)):
        row = skills.get(sid)
        if not row or row.get("category") == "特性":
            continue
        cat = row.get("category")
        if cat == "攻击":
            cat = "物理" if row.get("damage_class") == "物攻" else "魔法"
        else:
            cat = "变化"
        skills_out.append({
            "name": row["name"],
            "type": type_name(row.get("element") or "") if row.get("element") != "无系别" else "",
            "category": cat,
            "power": row.get("power") or 0,
            "pp": 0,
            "accuracy": 100,
            "energy": row.get("energy") or 0,
            "effect": row.get("desc") or "",
        })
    # 同名技能去重（保留先出现者）
    seen_names, deduped = set(), []
    for s in skills_out:
        if s["name"] not in seen_names:
            seen_names.add(s["name"])
            deduped.append(s)
    skills_out = deduped

    # ---- 进化链
    baseline_evo = json.load(open(os.path.join(WEB_DATA, "evolution_chains.json"), encoding="utf-8"))
    baseline_boss_names = {
        p["name"] for p in baseline_pets if p["id"] in set(baseline_evo["boss_excluded"])
    }
    boss_names = set(baseline_boss_names)
    for pid, row in catalog.items():
        if pid in data["targets_pet"] and row.get("is_lord_evolution"):
            boss_names.add(disp[pid])     # S5 新增首领形态
    boss_ids = sorted(p["id"] for p in pets_out if p["name"] in boss_names)

    chains_raw = []   # (members[pid], name, conditions, lord_branch_pids)
    seen_variant = set()
    for _eid, variants in data["evolutions"].items():
        if not isinstance(variants, list):
            variants = [variants]
        for var in variants:
            members = [m["id"] for m in var.get("chain") or [] if m.get("id") in catalog]
            if not members:
                continue
            sig = tuple(members)
            if sig in seen_variant:
                continue
            seen_variant.add(sig)
            conds = {}
            chain = var["chain"]
            for i in range(1, len(chain)):
                prev_t, cur = title_of[chain[i - 1]["id"]], chain[i]
                special = (evo_cond.get(prev_t) or {}).get(title_of[cur["id"]])
                if special:
                    conds[f"进化{i}"] = special
                elif cur.get("level") is not None:
                    conds[f"进化{i}"] = str(cur["level"])
            chains_raw.append({
                "members": members,
                "name": var.get("name") or f"{disp[members[0]]}进化链",
                "conditions": conds,
                "lords": [b["id"] for b in var.get("lord_branches") or [] if b.get("id") in catalog],
            })

    covered = set()
    for c in chains_raw:
        covered.update(c["members"])
    # 未被任何链覆盖的非首领精灵 → 单成员链（与基线口径一致）
    for pid, row in catalog.items():
        if pid not in covered and disp[pid] not in boss_names:
            chains_raw.append({"members": [pid], "name": f"{disp[pid]}进化链",
                               "conditions": {}, "lords": []})
            covered.add(pid)
    chains_raw.sort(key=lambda c: (int(catalog[c["members"][0]]["number"]), title_of[c["members"][0]]))

    chains_out, pet_chain_map = [], {}
    for i, c in enumerate(chains_raw, 1):
        cid = f"chain_{i:03d}"
        mids = [pid_to_id[p] for p in c["members"]]
        apex_pid = max(c["members"], key=lambda p: catalog[p].get("stage") or 0)
        chains_out.append({
            "id": cid,
            "name": c["name"],
            "members": mids,
            "member_names": [disp[p] for p in c["members"]],
            "member_stats": {str(pid_to_id[p]): pet_by_id[pid_to_id[p]]["stats"]["total"] for p in c["members"]},
            "apex_id": pid_to_id[apex_pid],
            "apex_name": disp[apex_pid],
            "conditions": c["conditions"],
            "_origin": "nrc-evolutions",
        })
        for p in c["members"]:
            pet_chain_map.setdefault(str(pid_to_id[p]), cid)

    # 候选池：链顶端，排除首领；再按 sync_data.py 的规则过滤同名前阶
    raw_candidates = sorted({c["apex_id"] for c in chains_out} - set(boss_ids))
    pre_names = set()
    for c in chains_out:
        if len(c["members"]) > 1:
            for j, mid in enumerate(c["members"]):
                if mid != c["apex_id"]:
                    pre_names.add(c["member_names"][j])
    id_to_name = {}
    for c in chains_out:
        for j, mid in enumerate(c["members"]):
            id_to_name[mid] = c["member_names"][j]
    candidate_ids = [i for i in raw_candidates if id_to_name.get(i, "") not in pre_names]

    evo_out = {
        "total_chains": len(chains_out),
        "multi_member_chains": sum(1 for c in chains_out if len(c["members"]) > 1),
        "single_member_chains": sum(1 for c in chains_out if len(c["members"]) == 1),
        "total_pets_covered": len({m for c in chains_out for m in c["members"]}),
        "apex_count": len({c["apex_id"] for c in chains_out}),
        "candidate_pool_size": len(candidate_ids),
        "candidate_ids": candidate_ids,
        "boss_excluded": boss_ids,
        "source": "BWIKI nrc Module:Pets/data/Evolutions + 精灵图鉴/S5 分片（2026-11-08 重建）",
        "pet_chain_map": pet_chain_map,
        "chains": chains_out,
    }

    stats_out = {
        "total_pets": len(pets_out),
        "total_skills": len(skills_out),
        "total_learnset": len(learnset_out),
        "types": dict(Counter(p["type_primary"] for p in pets_out)),
    }

    def dump(name, obj):
        with open(os.path.join(WEB_DATA, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)

    dump("pets.json", pets_out)
    dump("skills.json", skills_out)
    dump("learnset.json", learnset_out)
    dump("evolution_chains.json", evo_out)
    dump("stats.json", stats_out)
    cand_ts = (
        "// 自动生成 — 候选ID ∩ pets.json，已排除重复前阶形态\n"
        f"// 原始候选 {len(raw_candidates)} → 过滤后 {len(candidate_ids)} 只\n"
        "// 运行 scraper/nrc_extract.py 重新生成\n"
        f"export const APEX_IDS: Set<number> = new Set({json.dumps(candidate_ids)});\n"
    )
    with open(os.path.join(WEB_DATA, "candidate_ids.ts"), "w", encoding="utf-8") as f:
        f.write(cand_ts)

    # ---- diff 摘要
    new_names = [p["name"] for p in pets_out if p["name"] not in baseline_by_name]
    gone_names = [n for n in baseline_by_name if n not in {p["name"] for p in pets_out}]
    season_of = {}
    for pid, row in catalog.items():
        season_of[disp[pid]] = (overview.get(pid) or {}).get("season") or "none"
    print(json.dumps({
        "pets_total": len(pets_out), "skills_total": len(skills_out),
        "learnset_total": len(learnset_out), "chains_total": len(chains_out),
        "candidate_pool": len(candidate_ids), "boss_excluded": boss_ids,
        "new_pets_count": len(new_names),
        "new_by_season": dict(Counter(season_of.get(n, "?") for n in new_names)),
        "new_pets": new_names,
        "baseline_names_missing": gone_names,
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

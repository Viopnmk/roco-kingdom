import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import type { Skill } from "../types";
import { skills, learnset } from "../data";
import { TYPES } from "../types";
import { getTypeColor } from "../utils/typeChart";
import SkillTable from "../components/SkillTable";

const SOURCE_LABELS: Record<string, string> = {
  level: "升级",
  stone: "技能石",
  bloodline: "血脉",
};

export default function SkillPage() {
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null);

  const filtered = useMemo(() => {
    let result = [...skills];
    if (search.trim()) {
      const kw = search.trim().toLowerCase();
      result = result.filter(
        (s) =>
          s.name.toLowerCase().includes(kw) ||
          s.effect.toLowerCase().includes(kw)
      );
    }
    if (typeFilter) {
      result = result.filter((s) => s.type === typeFilter);
    }
    result.sort((a, b) => a.name.localeCompare(b.name, "zh"));
    return result;
  }, [search, typeFilter]);

  const learnsetBySkill = useMemo(() => {
    const map: Record<string, { pet_id: number; pet_name: string; source: string }[]> = {};
    for (const entry of learnset) {
      if (!map[entry.skill_name]) map[entry.skill_name] = [];
      map[entry.skill_name].push(entry);
    }
    return map;
  }, []);

  const skillPets = selectedSkill
    ? (learnsetBySkill[selectedSkill.name] || []).sort((a, b) => a.pet_id - b.pet_id)
    : [];

  const petsBySource = useMemo(() => {
    const map: Record<string, typeof skillPets> = {};
    for (const p of skillPets) {
      if (!map[p.source]) map[p.source] = [];
      map[p.source].push(p);
    }
    return map;
  }, [skillPets]);

  if (!skills.length) {
    return (
      <div className="empty-state">
        <h3>还没有技能数据</h3>
        <p>请先运行爬虫获取数据</p>
      </div>
    );
  }

  const sourceOrder = ["level", "stone", "bloodline"];

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>技能列表</h2>
      <div className="search-bar">
        <input
          type="text"
          placeholder="搜索技能名称、效果..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      <div className="filter-row">
        <button
          className={`filter-chip ${!typeFilter ? "selected" : ""}`}
          onClick={() => setTypeFilter("")}
        >
          全部
        </button>
        {TYPES.map((t) => (
          <button
            key={t}
            className={`filter-chip ${typeFilter === t ? "selected" : ""}`}
            style={
              typeFilter === t
                ? { background: getTypeColor(t), borderColor: getTypeColor(t) }
                : {}
            }
            onClick={() => setTypeFilter(typeFilter === t ? "" : t)}
          >
            {t}
          </button>
        ))}
      </div>
      <p style={{ color: "var(--text-dim)", fontSize: 13, marginBottom: 16 }}>
        共 {filtered.length} 个技能，点击技能可查看详情
      </p>
      <SkillTable skills={filtered} onSkillClick={setSelectedSkill} />

      {/* 技能详情面板 */}
      {selectedSkill && (
        <div className="skill-detail-panel">
          <div className="skill-detail-header">
            <h3>{selectedSkill.name}</h3>
            <button
              className="back-btn"
              onClick={() => setSelectedSkill(null)}
            >
              关闭
            </button>
          </div>
          <div className="skill-detail-meta">
            <span className="type-badge" style={{ background: getTypeColor(selectedSkill.type) }}>
              {selectedSkill.type}
            </span>
            <span style={{ color: "#42a5f5" }}>
              {selectedSkill.category}
            </span>
            <span>威力: {selectedSkill.power || "-"}</span>
            <span>能耗: {selectedSkill.energy || "-"}</span>
          </div>
          <div className="skill-detail-effect">
            <strong>效果：</strong>
            {selectedSkill.effect || "暂无描述"}
          </div>

          {/* 可学习该技能的精灵列表 */}
          <div className="skill-detail-learnset">
            <h4>可学习精灵 ({skillPets.length})</h4>
            {sourceOrder.map((src) => {
              const pets = petsBySource[src];
              if (!pets || !pets.length) return null;
              return (
                <div key={src} style={{ marginBottom: 10 }}>
                  <span style={{ fontSize: 12, color: "var(--text-dim)", marginRight: 8 }}>
                    {SOURCE_LABELS[src]} ({pets.length}):
                  </span>
                  {pets.map((p) => (
                    <Link
                      key={`${p.pet_id}-${p.source}`}
                      to={`/pet/${p.pet_id}`}
                      className="skill-pet-link"
                      onClick={() => setSelectedSkill(null)}
                    >
                      {p.pet_name}
                    </Link>
                  ))}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

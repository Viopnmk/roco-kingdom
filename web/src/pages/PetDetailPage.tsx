import { useParams, useNavigate, Link } from "react-router-dom";
import { useState } from "react";
import type { Skill } from "../types";
import { pets, skills, learnset } from "../data";
import { getTypeColor, getWeaknesses } from "../utils/typeChart";
import StatsRadar from "../components/StatsRadar";
import SkillTable from "../components/SkillTable";

const SOURCE_LABELS: Record<string, string> = {
  level: "升级技能",
  stone: "技能石",
  bloodline: "血脉技能",
};

const SHORT_SOURCE: Record<string, string> = {
  level: "升级",
  stone: "技能石",
  bloodline: "血脉",
};

const SOURCE_ORDER = ["level", "stone", "bloodline"] as const;

export default function PetDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [skillTab, setSkillTab] = useState<string>("level");
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null);
  const pet = pets.find((p) => String(p.id) === id);

  if (!pet) {
    return (
      <div>
        <button className="back-btn" onClick={() => navigate("/")}>
          &larr; 返回列表
        </button>
        <div className="empty-state">
          <h3>精灵不存在</h3>
          <p>未找到编号为 {id} 的精灵</p>
        </div>
      </div>
    );
  }

  const types = [pet.type_primary, pet.type_secondary].filter(Boolean) as string[];
  const weaknesses = pet.type_secondary
    ? getWeaknesses([pet.type_primary])
    : getWeaknesses([pet.type_primary]);

  // 按来源分组技能，保持精灵原始技能顺序
  const skillsBySource: Record<string, string[]> = {
    level: pet.skills || [],
    stone: pet.stone_skills || [],
    bloodline: pet.bloodline_skills || [],
  };
  const skillMap = new Map(skills.map((s) => [s.name, s]));
  const petSkillsBySource: Record<string, typeof skills> = {};
  for (const src of SOURCE_ORDER) {
    petSkillsBySource[src] = skillsBySource[src]
      .map((name) => skillMap.get(name))
      .filter((s): s is (typeof skills)[number] => s != null);
  }
  const totalSkills = Object.values(petSkillsBySource).reduce((sum, arr) => sum + arr.length, 0);
  const total = pet.stats.total;

  // 点击技能时查找学习面
  const learnsetBySkill: Record<string, { pet_id: number; pet_name: string; source: string }[]> = {};
  for (const entry of learnset) {
    if (!learnsetBySkill[entry.skill_name]) learnsetBySkill[entry.skill_name] = [];
    learnsetBySkill[entry.skill_name].push(entry);
  }
  const skillPets = selectedSkill
    ? (learnsetBySkill[selectedSkill.name] || []).sort((a, b) => a.pet_id - b.pet_id)
    : [];
  const skillPetsBySource: Record<string, typeof skillPets> = {};
  for (const p of skillPets) {
    if (!skillPetsBySource[p.source]) skillPetsBySource[p.source] = [];
    skillPetsBySource[p.source].push(p);
  }

  return (
    <div>
      <button className="back-btn" onClick={() => navigate("/")}>
        &larr; 返回列表
      </button>

      {/* Header */}
      <div className="detail-header">
        <div className="detail-info">
          <div className="detail-number">No.{pet.id || "???"}</div>
          <h1 className="detail-name">{pet.name}</h1>
          <div className="detail-types">
            {types.map((t) => (
              <span key={t} className="type-badge" style={{ background: getTypeColor(t) }}>
                {t}
              </span>
            ))}
          </div>
          {pet.description && (
            <p style={{ color: "var(--text-dim)", fontSize: 13, lineHeight: 1.6 }}>
              {pet.description}
            </p>
          )}
          {pet.ability && (
            <p style={{ marginTop: 8, fontSize: 13 }}>
              <span style={{ color: "var(--text-dim)" }}>特性：</span>
              {pet.ability}
            </p>
          )}
        </div>
        <StatsRadar stats={pet.stats} />
      </div>

      {/* 种族值 */}
      <div className="detail-section">
        <h3>
          种族值
          <span style={{ marginLeft: 8, fontSize: 14, color: "var(--accent)" }}>
            总和 {total}
          </span>
        </h3>
        {(["hp", "atk", "defense", "sp_atk", "sp_def", "speed"] as const).map(
          (key) => {
            const labels: Record<string, string> = {
              hp: "生命",
              atk: "物攻",
              defense: "物防",
              sp_atk: "魔攻",
              sp_def: "魔防",
              speed: "速度",
            };
            const val = pet.stats[key];
            const pct = Math.min((val / 180) * 100, 100);
            return (
              <div key={key} className="stat-bar-row">
                <span className="stat-bar-label">{labels[key]}</span>
                <span className="stat-bar-val">{val}</span>
                <div className="stat-bar-track">
                  <div
                    className="stat-bar-fill"
                    style={{
                      width: `${pct}%`,
                      background:
                        val >= 120 ? "#ef5350" : val >= 90 ? "#ff9800" : "#66bb6a",
                    }}
                  />
                </div>
              </div>
            );
          }
        )}
      </div>

      {/* 进化链 */}
      {pet.evolution_chain && pet.evolution_chain.length > 0 && (
        <div className="detail-section">
          <h3>进化链</h3>
          <div className="evo-chain">
            {pet.evolution_chain.map((stage, i) => (
              <span key={stage.name}>
                {i > 0 && <span className="evo-arrow"> &rarr; </span>}
                <span className="evo-stage">
                  {stage.name}
                  {stage.level && <div className="evo-level">Lv.{stage.level}</div>}
                </span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* 技能 - 按来源分类 */}
      <div className="detail-section">
        <h3>技能 ({totalSkills})</h3>
        <div className="filter-row" style={{ marginBottom: 12 }}>
          {SOURCE_ORDER.map((src) => {
            const count = petSkillsBySource[src].length;
            if (count === 0) return null;
            return (
              <button
                key={src}
                className={`filter-chip ${skillTab === src ? "selected" : ""}`}
                onClick={() => setSkillTab(src)}
              >
                {SOURCE_LABELS[src]} ({count})
              </button>
            );
          })}
        </div>
        <SkillTable skills={petSkillsBySource[skillTab] || []} onSkillClick={setSelectedSkill} />
      </div>

      {/* 技能详情弹窗 */}
      {selectedSkill && (
        <div className="detail-section">
          <div className="skill-detail-panel">
            <div className="skill-detail-header">
              <h3>{selectedSkill.name}</h3>
              <button className="back-btn" onClick={() => setSelectedSkill(null)}>关闭</button>
            </div>
            <div className="skill-detail-meta">
              <span className="type-badge" style={{ background: getTypeColor(selectedSkill.type) }}>{selectedSkill.type}</span>
              <span>分类: {selectedSkill.category}</span>
              <span>威力: {selectedSkill.power}</span>
              <span>能耗: {selectedSkill.energy}</span>
            </div>
            <div className="skill-detail-effect">
              <strong>效果：</strong>{selectedSkill.effect || "暂无描述"}
            </div>
            <div className="skill-detail-learnset">
              <h4>可学习精灵 ({skillPets.length})</h4>
              {SOURCE_ORDER.map((src) => {
                const list = skillPetsBySource[src];
                if (!list || !list.length) return null;
                return (
                  <div key={src} style={{ marginBottom: 10 }}>
                    <span style={{ fontSize: 12, color: "var(--text-dim)", marginRight: 8 }}>
                      {SHORT_SOURCE[src]} ({list.length}):
                    </span>
                    {list.map((p) => (
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
        </div>
      )}

      {/* 属性克制 */}
      <div className="detail-section">
        <h3>属性克制</h3>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {weaknesses
            .filter((w) => w.multiplier > 1)
            .map((w) => (
              <span
                key={w.type}
                className="weakness-badge"
                style={{
                  background: "rgba(239,83,80,0.2)",
                  color: "#ef5350",
                  border: "1px solid rgba(239,83,80,0.4)",
                }}
              >
                弱 {w.type} {w.multiplier}x
              </span>
            ))}
          {weaknesses
            .filter((w) => w.multiplier < 1 && w.multiplier > 0)
            .map((w) => (
              <span
                key={w.type}
                className="weakness-badge"
                style={{
                  background: "rgba(102,187,106,0.2)",
                  color: "#66bb6a",
                  border: "1px solid rgba(102,187,106,0.4)",
                }}
              >
                抗 {w.type} {w.multiplier}x
              </span>
            ))}
          {weaknesses
            .filter((w) => w.multiplier === 0)
            .map((w) => (
              <span
                key={w.type}
                className="weakness-badge"
                style={{
                  background: "rgba(136,136,136,0.2)",
                  color: "#888",
                  border: "1px solid rgba(136,136,136,0.4)",
                }}
              >
                免疫 {w.type}
              </span>
            ))}
        </div>
      </div>

      {/* 获取方式 */}
      {pet.how_to_get && (
        <div className="detail-section">
          <h3>获取方式</h3>
          <p style={{ fontSize: 13, color: "var(--text-dim)" }}>{pet.how_to_get}</p>
        </div>
      )}
    </div>
  );
}

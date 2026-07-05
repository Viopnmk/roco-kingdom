import { useState, useMemo } from "react";
import type { Pet, Skill, PetType } from "../types";
import PetPicker from "../components/PetPicker";
import SkillPicker from "../components/SkillPicker";
import { getTypeColor, TYPE_CHART, calcEffectiveness } from "../utils/typeChart";
import { TYPES } from "../types";

interface TeamMember {
  pet: Pet;
  selectedSkills: Skill[];
}

type TeamSlots = (TeamMember | null)[];

const EMPTY_SLOTS: TeamSlots = [null, null, null, null, null, null];

export default function TeamBuilderPage() {
  const [slots, setSlots] = useState<TeamSlots>(EMPTY_SLOTS);
  const [pickingSlot, setPickingSlot] = useState<number | null>(null);
  const [skillSlot, setSkillSlot] = useState<number | null>(null);

  const handleSelectPet = (pet: Pet) => {
    if (pickingSlot === null) return;
    setSlots((prev) => {
      const next = [...prev];
      next[pickingSlot] = { pet, selectedSkills: [] };
      return next;
    });
    setPickingSlot(null);
  };

  const handleRemovePet = (idx: number) => {
    setSlots((prev) => {
      const next = [...prev];
      next[idx] = null;
      return next;
    });
  };

  const handleSkillConfirm = (newSkills: Skill[]) => {
    if (skillSlot === null) return;
    setSlots((prev) => {
      const next = [...prev];
      const member = next[skillSlot];
      if (member) {
        next[skillSlot] = { ...member, selectedSkills: newSkills };
      }
      return next;
    });
  };

  // 打击面分析
  const coverage = useMemo(() => {
    const result: Record<string, { maxMult: number; skills: string[] }> = {};
    for (const defType of TYPES) {
      result[defType] = { maxMult: 1, skills: [] };
    }
    for (const slot of slots) {
      if (!slot) continue;
      for (const skill of slot.selectedSkills) {
        const atkType = skill.type as PetType;
        if (!atkType) continue;
        for (const defType of TYPES) {
          const m = calcEffectiveness(atkType as PetType, [defType as PetType]);
          const cur = result[defType];
          if (m > cur.maxMult) {
            cur.maxMult = m;
            cur.skills = [skill.name];
          } else if (m === cur.maxMult && m > 1) {
            cur.skills.push(skill.name);
          }
        }
      }
    }
    return result;
  }, [slots]);

  // 被打击面分析
  const weakness = useMemo(() => {
    const result: Record<string, { maxMult: number; pets: string[] }> = {};
    for (const atkType of TYPES) {
      result[atkType] = { maxMult: 1, pets: [] };
    }
    for (const slot of slots) {
      if (!slot) continue;
      const defTypes = [slot.pet.type_primary, slot.pet.type_secondary]
        .filter(Boolean) as PetType[];
      for (const atkType of TYPES) {
        let m = 1;
        for (const dt of defTypes) {
          m *= TYPE_CHART[atkType as PetType]?.[dt] ?? 1;
        }
        const cur = result[atkType];
        if (m > cur.maxMult) {
          cur.maxMult = m;
          cur.pets = [slot.pet.name];
        } else if (m === cur.maxMult && m > 1) {
          cur.pets.push(slot.pet.name);
        }
      }
    }
    return result;
  }, [slots]);

  const activeMembers = slots.filter((s): s is TeamMember => s !== null);

  return (
    <div>
      <h2 style={{ marginBottom: 20 }}>编队</h2>

      {/* 6个槽位 */}
      <div className="team-slots">
        {slots.map((slot, idx) => {
          if (!slot) {
            return (
              <div
                key={idx}
                className="team-slot team-slot-empty"
                onClick={() => setPickingSlot(idx)}
              >
                <span className="team-slot-plus">+</span>
                <span className="team-slot-hint">添加精灵</span>
              </div>
            );
          }
          const { pet, selectedSkills } = slot;
          const types = [pet.type_primary, pet.type_secondary].filter(Boolean) as string[];
          return (
            <div key={idx} className="team-slot team-slot-filled">
              <button
                className="team-slot-remove"
                onClick={(e) => { e.stopPropagation(); handleRemovePet(idx); }}
              >
                ×
              </button>
              <div
                className="team-slot-pet"
                onClick={() => setPickingSlot(idx)}
              >
                <span className="team-slot-id">No.{pet.id || "?"}</span>
                <span className="team-slot-name">{pet.name}</span>
                <span className="team-slot-types">
                  {types.map((t) => (
                    <span key={t} className="type-badge" style={{ background: getTypeColor(t) }}>
                      {t}
                    </span>
                  ))}
                </span>
                <span className="team-slot-total">种族值 {pet.stats.total}</span>
              </div>
              <div className="team-slot-skills">
                {selectedSkills.length === 0 ? (
                  <span className="team-slot-skills-empty">未配置技能</span>
                ) : (
                  selectedSkills.map((sk) => (
                    <span key={sk.name} className="type-badge" style={{ background: getTypeColor(sk.type) }}>
                      {sk.name}
                    </span>
                  ))
                )}
              </div>
              <button
                className="btn btn-small btn-primary"
                onClick={() => setSkillSlot(idx)}
              >
                配置技能 ({selectedSkills.length}/4)
              </button>
            </div>
          );
        })}
      </div>

      {/* 队伍分析区 */}
      {activeMembers.length > 0 && (
        <div className="team-analysis">
          <h3 style={{ marginBottom: 16 }}>队伍分析</h3>
          <div className="analysis-grid">
            {/* 打击面 */}
            <div className="analysis-card">
              <h4 className="analysis-card-title">打击面</h4>
              <p className="analysis-card-desc">
                队伍技能可克制的属性（绿色=有克制手段）
              </p>
              <div className="analysis-tags">
                {Object.entries(coverage).map(([defType, info]) => {
                  const covered = info.maxMult > 1;
                  return (
                    <span
                      key={defType}
                      className="analysis-tag"
                      style={{
                        background: covered
                          ? "rgba(102,187,106,0.2)"
                          : "rgba(255,255,255,0.05)",
                        border: covered
                          ? "1px solid rgba(102,187,106,0.4)"
                          : "1px solid var(--border)",
                        color: covered ? "#66bb6a" : "var(--text-dim)",
                      }}
                      title={
                        covered
                          ? `最大 ${info.maxMult}x（${info.skills.slice(0, 5).join("、")}）`
                          : "无有效克制手段"
                      }
                    >
                      {defType} {covered ? `${info.maxMult}x` : ""}
                    </span>
                  );
                })}
              </div>
            </div>

            {/* 防守弱点 */}
            <div className="analysis-card">
              <h4 className="analysis-card-title">防守弱点</h4>
              <p className="analysis-card-desc">
                按威胁程度从高到低排列
              </p>
              <div className="analysis-weak-list">
                {Object.entries(weakness)
                  .filter(([, info]) => info.maxMult > 1)
                  .sort(([, a], [, b]) => b.maxMult - a.maxMult)
                  .map(([atkType, info]) => (
                    <div key={atkType} className="analysis-weak-row">
                      <span
                        className="type-badge"
                        style={{ background: getTypeColor(atkType) }}
                      >
                        {atkType}
                      </span>
                      <span
                        style={{
                          color: info.maxMult >= 4 ? "#ef5350" : "#ff9800",
                          fontWeight: 600,
                          fontSize: 14,
                        }}
                      >
                        {info.maxMult}x
                      </span>
                      <span style={{ fontSize: 12, color: "var(--text-dim)", marginLeft: 4 }}>
                        ({info.pets.join("、")})
                      </span>
                    </div>
                  ))}
                {Object.values(weakness).filter((w) => w.maxMult > 1).length === 0 && (
                  <p style={{ color: "var(--text-dim)", fontSize: 13 }}>
                    队伍没有明显弱点
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 弹窗 */}
      {pickingSlot !== null && (
        <PetPicker
          onSelect={handleSelectPet}
          onClose={() => setPickingSlot(null)}
        />
      )}
      {skillSlot !== null && slots[skillSlot] && (
        <SkillPicker
          pet={slots[skillSlot]!.pet}
          selected={slots[skillSlot]!.selectedSkills}
          onConfirm={handleSkillConfirm}
          onClose={() => setSkillSlot(null)}
        />
      )}
    </div>
  );
}

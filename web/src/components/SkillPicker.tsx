import { useState, useMemo } from "react";
import type { Pet, Skill } from "../types";
import { skills, learnset } from "../data";
import { getTypeColor } from "../utils/typeChart";

interface Props {
  pet: Pet;
  selected: Skill[];
  onConfirm: (skills: Skill[]) => void;
  onClose: () => void;
}

const SOURCE_LABELS: Record<string, string> = {
  level: "升级技能",
  stone: "技能石",
  bloodline: "血脉技能",
};

const SOURCE_ORDER = ["level", "stone", "bloodline"] as const;

const CATEGORY_COLORS: Record<string, string> = {
  "物理": "#ef5350",
  "魔法": "#42a5f5",
  "变化": "#ababab",
};

export default function SkillPicker({ pet, selected, onConfirm, onClose }: Props) {
  const [tab, setTab] = useState<string>("level");
  const [localSelected, setLocalSelected] = useState<Skill[]>(() => [...selected]);

  const skillsBySource = useMemo(() => {
    const map: Record<string, Skill[]> = { level: [], stone: [], bloodline: [] };
    const skillMap = new Map(skills.map((s) => [s.name, s]));
    const entries = learnset.filter((e) => e.pet_id === pet.id);
    for (const e of entries) {
      const skill = skillMap.get(e.skill_name);
      if (skill && SOURCE_ORDER.includes(e.source as typeof SOURCE_ORDER[number])) {
        map[e.source].push(skill);
      }
    }
    return map;
  }, [pet.id]);

  const displaySkills = skillsBySource[tab] || [];
  const selectedNames = new Set(localSelected.map((s) => s.name));

  const toggleSkill = (skill: Skill) => {
    if (selectedNames.has(skill.name)) {
      setLocalSelected((prev) => prev.filter((s) => s.name !== skill.name));
    } else if (localSelected.length < 4) {
      setLocalSelected((prev) => [...prev, skill]);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal modal-wide" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>配置技能 — {pet.name}</h3>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span style={{ fontSize: 12, color: "var(--text-dim)" }}>
              已选 {localSelected.length}/4
            </span>
            <button className="modal-close" onClick={onClose}>×</button>
          </div>
        </div>

        <div className="filter-row" style={{ marginBottom: 12 }}>
          {SOURCE_ORDER.map((src) => {
            const count = skillsBySource[src].length;
            if (count === 0) return null;
            return (
              <button
                key={src}
                className={`filter-chip ${tab === src ? "selected" : ""}`}
                onClick={() => setTab(src)}
              >
                {SOURCE_LABELS[src]} ({count})
              </button>
            );
          })}
        </div>

        <div className="skill-picker-list">
          {displaySkills.map((sk) => {
            const isSelected = selectedNames.has(sk.name);
            const isFull = localSelected.length >= 4 && !isSelected;
            return (
              <div
                key={sk.name}
                className={`skill-picker-item ${isSelected ? "checked" : ""} ${isFull ? "disabled" : ""}`}
                onClick={() => !isFull && toggleSkill(sk)}
              >
                <span className={`skill-picker-check ${isSelected ? "on" : ""}`}>
                  {isSelected ? "✓" : ""}
                </span>
                <span style={{ fontWeight: 600, minWidth: 100 }}>{sk.name}</span>
                <span className="type-badge" style={{ background: getTypeColor(sk.type) }}>
                  {sk.type}
                </span>
                <span style={{ color: CATEGORY_COLORS[sk.category] || "#888", fontSize: 12, fontWeight: 600, minWidth: 36 }}>
                  {sk.category}
                </span>
                <span style={{ fontSize: 12, minWidth: 40 }}>
                  威力:{sk.power || "-"}
                </span>
                <span style={{ fontSize: 12, minWidth: 40 }}>
                  能耗:{sk.energy || "-"}
                </span>
                <span style={{ fontSize: 11, color: "var(--text-dim)", flex: 1, textAlign: "right" }}>
                  {sk.effect.slice(0, 30)}{sk.effect.length > 30 ? "..." : ""}
                </span>
              </div>
            );
          })}
          {displaySkills.length === 0 && (
            <p style={{ textAlign: "center", color: "var(--text-dim)", padding: 20 }}>
              该分类无可用技能
            </p>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>取消</button>
          <button className="btn btn-primary" onClick={() => { onConfirm(localSelected); onClose(); }}>
            确定 ({localSelected.length}/4)
          </button>
        </div>
      </div>
    </div>
  );
}

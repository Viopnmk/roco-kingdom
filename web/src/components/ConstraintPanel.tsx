import { useState, useEffect } from "react";
import type { Pet } from "../types";
import { pets } from "../data";
import { TYPES } from "../types";
import { getTypeColor } from "../utils/typeChart";
import PetPicker from "./PetPicker";

export interface Constraints {
  team_type: string;       // "" | "synergy" | "balanced"
  must_include: number[];
  must_exclude: number[];
  prefer_type: string;
  style: string;
  top_k: number;
  pop_size: number;
  generations: number;
}

export const STYLE_OPTIONS = [
  { value: "", label: "不限" },
  { value: "灼烧体系", label: "灼烧体系" },
  { value: "中毒消耗", label: "中毒消耗" },
  { value: "冻结控场", label: "冻结控场" },
  { value: "星陨爆发", label: "星陨爆发" },
  { value: "天气队", label: "天气队" },
  { value: "传动体系", label: "传动体系" },
  { value: "印记运营", label: "印记运营" },
  { value: "应对返还", label: "应对返还" },
  { value: "先手压制", label: "先手压制" },
  { value: "吸血续航", label: "吸血续航" },
  { value: "增益传递", label: "增益传递" },
  { value: "巧变切换", label: "巧变切换" },
  { value: "萌化退化", label: "萌化退化" },
];

export const defaultConstraints: Constraints = {
  team_type: "",
  must_include: [],
  must_exclude: [],
  prefer_type: "",
  style: "",
  top_k: 10,
  pop_size: 100,
  generations: 100,
};

interface Props {
  constraints: Constraints;
  onChange: (c: Constraints) => void;
  onSearch: () => void;
  loading: boolean;
}

/** 按 ID 查精灵 */
function getPetById(id: number): Pet | undefined {
  return pets.find((p) => p.id === id);
}

export default function ConstraintPanel({
  constraints,
  onChange,
  onSearch,
  loading,
}: Props) {
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [pickerTarget, setPickerTarget] = useState<"include" | "exclude" | null>(null);

  // 切换到平衡队时自动清空战术风格
  useEffect(() => {
    if (constraints.team_type === "balanced" && constraints.style !== "") {
      onChange({ ...constraints, style: "" });
    }
  }, [constraints.team_type]);

  const set = (patch: Partial<Constraints>) =>
    onChange({ ...constraints, ...patch });

  const handlePetPicked = (pet: Pet) => {
    if (pickerTarget === "include") {
      if (!constraints.must_include.includes(pet.id)) {
        set({ must_include: [...constraints.must_include, pet.id] });
      }
    } else if (pickerTarget === "exclude") {
      if (!constraints.must_exclude.includes(pet.id)) {
        set({ must_exclude: [...constraints.must_exclude, pet.id] });
      }
    }
    setPickerTarget(null);
  };

  const removeInclude = (id: number) => {
    set({ must_include: constraints.must_include.filter((i) => i !== id) });
  };

  const removeExclude = (id: number) => {
    set({ must_exclude: constraints.must_exclude.filter((i) => i !== id) });
  };

  return (
    <div className="constraint-panel">
      <h3 className="constraint-title">搜索条件</h3>

      {/* 配队类型 */}
      <div className="constraint-section">
        <label className="constraint-label">配队类型</label>
        <div className="constraint-chips">
          <span
            className={`filter-chip ${constraints.team_type === "" ? "selected" : ""}`}
            onClick={() => set({ team_type: "", style: "" })}
          >
            不限
          </span>
          <span
            className={`filter-chip ${constraints.team_type === "synergy" ? "selected" : ""}`}
            onClick={() => set({ team_type: "synergy" })}
          >
            体系队
          </span>
          <span
            className={`filter-chip ${constraints.team_type === "balanced" ? "selected" : ""}`}
            onClick={() => set({ team_type: "balanced" })}
          >
            平衡队
          </span>
        </div>
        <p className="constraint-hint" style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 4 }}>
          {constraints.team_type === "synergy"
            ? "以单一属性为核心，通过技能联动配队"
            : constraints.team_type === "balanced"
            ? "属性分散、打击面广泛，应对各种队伍"
            : "不限定配队策略"}
        </p>
      </div>

      {/* 战术风格（仅体系队时显示） */}
      {constraints.team_type !== "balanced" && (
      <div className="constraint-section">
        <label className="constraint-label">战术风格</label>
        <select
          className="constraint-select"
          value={constraints.style}
          onChange={(e) => set({ style: e.target.value })}
        >
          {STYLE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>
      )}

      {/* 偏好属性 */}
      <div className="constraint-section">
        <label className="constraint-label">偏好属性</label>
        <div className="constraint-chips">
          <span
            className={`filter-chip ${constraints.prefer_type === "" ? "selected" : ""}`}
            onClick={() => set({ prefer_type: "" })}
          >
            不限
          </span>
          {TYPES.map((t) => (
            <span
              key={t}
              className={`filter-chip ${constraints.prefer_type === t ? "selected" : ""}`}
              style={
                constraints.prefer_type === t
                  ? { background: getTypeColor(t), borderColor: getTypeColor(t) }
                  : undefined
              }
              onClick={() => set({ prefer_type: constraints.prefer_type === t ? "" : t })}
            >
              {t}
            </span>
          ))}
        </div>
      </div>

      {/* 必含精灵 */}
      <div className="constraint-section">
        <label className="constraint-label">必含精灵</label>
        <div className="constraint-pet-chips">
          {constraints.must_include.map((id) => {
            const pet = getPetById(id);
            return (
              <span key={id} className="constraint-pet-chip">
                {pet ? `${pet.name} (#${id})` : `#${id}`}
                <button className="constraint-chip-x" onClick={() => removeInclude(id)}>
                  ×
                </button>
              </span>
            );
          })}
          <button
            className="constraint-add-btn"
            onClick={() => setPickerTarget("include")}
            disabled={constraints.must_include.length >= 6}
          >
            + 添加
          </button>
        </div>
      </div>

      {/* 排除精灵 */}
      <div className="constraint-section">
        <label className="constraint-label">排除精灵</label>
        <div className="constraint-pet-chips">
          {constraints.must_exclude.map((id) => {
            const pet = getPetById(id);
            return (
              <span key={id} className="constraint-pet-chip constraint-pet-chip-exclude">
                {pet ? `${pet.name} (#${id})` : `#${id}`}
                <button className="constraint-chip-x" onClick={() => removeExclude(id)}>
                  ×
                </button>
              </span>
            );
          })}
          <button
            className="constraint-add-btn"
            onClick={() => setPickerTarget("exclude")}
          >
            + 添加
          </button>
        </div>
      </div>

      {/* 高级选项 */}
      <div className="constraint-section">
        <button
          className="constraint-toggle"
          onClick={() => setShowAdvanced(!showAdvanced)}
        >
          {showAdvanced ? "▾" : "▸"} 高级选项
        </button>
        {showAdvanced && (
          <div className="constraint-advanced">
            <div className="constraint-row">
              <span className="constraint-label">返回数量</span>
              <select
                className="constraint-select"
                value={constraints.top_k}
                onChange={(e) => set({ top_k: Number(e.target.value) })}
              >
                {[3, 5, 10, 20, 30].map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </select>
            </div>
            <div className="constraint-row">
              <span className="constraint-label">种群大小</span>
              <input
                type="range"
                min={20}
                max={400}
                step={20}
                value={constraints.pop_size}
                onChange={(e) => set({ pop_size: Number(e.target.value) })}
              />
              <span className="constraint-val">{constraints.pop_size}</span>
            </div>
            <div className="constraint-row">
              <span className="constraint-label">进化代数</span>
              <input
                type="range"
                min={20}
                max={300}
                step={10}
                value={constraints.generations}
                onChange={(e) => set({ generations: Number(e.target.value) })}
              />
              <span className="constraint-val">{constraints.generations}</span>
            </div>
          </div>
        )}
      </div>

      {/* 搜索按钮 */}
      <button
        className="btn btn-primary constraint-search-btn"
        onClick={onSearch}
        disabled={loading}
      >
        {loading ? "搜索中..." : "搜索最优配队"}
      </button>

      {/* 精灵选择器 */}
      {pickerTarget !== null && (
        <PetPicker
          onSelect={handlePetPicked}
          onClose={() => setPickerTarget(null)}
        />
      )}
    </div>
  );
}

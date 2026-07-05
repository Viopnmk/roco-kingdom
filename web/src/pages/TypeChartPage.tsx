import { useState } from "react";
import { TYPES } from "../types";
import type { PetType } from "../types";
import {
  TYPE_CHART,
  TYPE_COLORS,
  getWeaknesses,
  calcEffectiveness,
} from "../utils/typeChart";

const EFF_LABELS: Record<number, string> = {
  2: "双倍克制",
  1.5: "1.5倍克制",
  1: "正常",
  0.5: "抵抗",
  0: "免疫",
};

function getEffClass(val: number): string {
  if (val === 2) return "eff-2";
  if (val === 1.5) return "eff-1-5";
  if (val === 1) return "eff-1";
  if (val === 0.5) return "eff-0-5";
  if (val === 0) return "eff-0";
  return "";
}

export default function TypeChartPage() {
  const [defType1, setDefType1] = useState<PetType>("火");
  const [defType2, setDefType2] = useState<PetType | "">("");

  const defTypes = [defType1, defType2].filter(Boolean) as PetType[];
  const weaknesses = getWeaknesses(defTypes);

  return (
    <div>
      <h2 style={{ marginBottom: 20 }}>属性克制表</h2>

      {/* 克制查询器 */}
      <div className="detail-section">
        <h3>克制查询</h3>
        <div className="weakness-selector">
          <span style={{ fontSize: 14 }}>防御方属性：</span>
          <select value={defType1} onChange={(e) => setDefType1(e.target.value as PetType)}>
            {TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <select value={defType2} onChange={(e) => setDefType2(e.target.value as PetType | "")}>
            <option value="">无</option>
            {TYPES.filter((t) => t !== defType1).map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <span style={{ fontSize: 14, color: "var(--text-dim)" }}>
            防御方属性组合：{defTypes.join(" + ") || "无"}
          </span>
        </div>

        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
          {weaknesses.map((w) => (
            <span
              key={w.type}
              className="weakness-badge"
              style={{
                background:
                  w.multiplier > 1
                    ? "rgba(239,83,80,0.2)"
                    : w.multiplier < 1 && w.multiplier > 0
                    ? "rgba(102,187,106,0.2)"
                    : "rgba(136,136,136,0.2)",
                color:
                  w.multiplier > 1
                    ? "#ef5350"
                    : w.multiplier < 1 && w.multiplier > 0
                    ? "#66bb6a"
                    : "#888",
              }}
            >
              {w.type} {w.multiplier}x
            </span>
          ))}
        </div>
      </div>

      {/* 完整克制矩阵 */}
      <div className="detail-section">
        <h3>完整克制矩阵</h3>
        <p style={{ color: "var(--text-dim)", fontSize: 12, marginBottom: 12 }}>
          行 = 攻击方属性，列 = 防御方属性
        </p>
        <div className="type-chart-wrapper">
          <table className="type-chart-table">
            <thead>
              <tr>
                <th>攻\防</th>
                {TYPES.map((t) => (
                  <th key={t} style={{ color: TYPE_COLORS[t], fontSize: 11 }}>
                    {t}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {TYPES.map((atk) => (
                <tr key={atk}>
                  <th style={{ color: TYPE_COLORS[atk], fontSize: 11 }}>{atk}</th>
                  {TYPES.map((def) => {
                    const val = TYPE_CHART[atk]?.[def] ?? 1;
                    return (
                      <td
                        key={def}
                        className={getEffClass(val)}
                        title={`${atk} → ${def}: ${val}x`}
                      >
                        {val}x
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div style={{ marginTop: 16, display: "flex", gap: 16, flexWrap: "wrap", fontSize: 12 }}>
          {Object.entries(EFF_LABELS).map(([val, label]) => (
            <span key={val} style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <span
                className={getEffClass(Number(val))}
                style={{
                  display: "inline-block",
                  width: 16,
                  height: 16,
                  borderRadius: 4,
                }}
              />
              {label}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

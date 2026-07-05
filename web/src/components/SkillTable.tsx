import type { Skill } from "../types";
import { getTypeColor } from "../utils/typeChart";

interface Props {
  skills: Skill[];
  onSkillClick?: (skill: Skill) => void;
}

const CATEGORY_COLORS: Record<string, string> = {
  "物理": "#ef5350",
  "魔法": "#42a5f5",
  "变化": "#ababab",
};

export default function SkillTable({ skills, onSkillClick }: Props) {
  if (!skills.length) {
    return <p style={{ color: "var(--text-dim)", fontSize: 14 }}>暂无技能数据</p>;
  }

  const hasPP = skills.some((s) => s.pp > 0);

  return (
    <div className="skill-table-wrapper">
      <table className={`skill-table${onSkillClick ? " skill-table-clickable" : ""}`}>
        <thead>
          <tr>
            <th>技能</th>
            <th>属性</th>
            <th>分类</th>
            <th>威力</th>
            {hasPP && <th>PP</th>}
            <th>命中</th>
            <th>能耗</th>
            <th>效果</th>
          </tr>
        </thead>
        <tbody>
          {skills.map((s) => (
            <tr
              key={s.name}
              onClick={() => onSkillClick?.(s)}
              style={onSkillClick ? { cursor: "pointer" } : undefined}
            >
              <td style={{ fontWeight: 600 }}>{s.name}</td>
              <td>
                <span className="type-badge" style={{ background: getTypeColor(s.type) }}>
                  {s.type}
                </span>
              </td>
              <td>
                <span style={{ color: CATEGORY_COLORS[s.category] || "#888", fontSize: 12, fontWeight: 600 }}>
                  {s.category}
                </span>
              </td>
              <td>{s.power}</td>
              {hasPP && <td>{s.pp}</td>}
              <td>{s.accuracy}</td>
              <td>{s.energy}</td>
              <td style={{ maxWidth: 260, fontSize: 12 }}>{s.effect}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

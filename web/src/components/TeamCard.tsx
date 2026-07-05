import type { OptimizeResult, ApiTeamMember, TeamScores } from "../types/api";
import { getTypeColor } from "../utils/typeChart";
import { pets } from "../data";

interface Props {
  result: OptimizeResult;
  rank: number;
}

/** 7维评分的显示名称与参考最大值（用于进度条百分比） */
const SCORE_META: { key: keyof TeamScores; label: string; max: number }[] = [
  { key: "coverage", label: "打击面", max: 25 },
  { key: "defense", label: "抗性互补", max: 12 },
  { key: "synergy", label: "联动", max: 100 },
  { key: "stats", label: "种族值", max: 45 },
  { key: "role_balance", label: "职责平衡", max: 12 },
  { key: "speed", label: "速度梯度", max: 12 },
  { key: "energy", label: "能量平衡", max: 12 },
];

/** 职责颜色 */
const ROLE_COLORS: Record<string, string> = {
  "物理输出": "#ef5350",
  "魔法输出": "#42a5f5",
  "双刀": "#ab47bc",
  "坦克": "#ffa726",
  "辅助": "#66bb6a",
  "控场": "#ec407a",
  "天气手": "#26c6da",
  "高速游击": "#ffee58",
  "一般": "#bdbdbd",
};

function getRoleColor(role: string): string {
  return ROLE_COLORS[role] || "#888";
}

function PetMini({ member, index }: { member: ApiTeamMember; index: number }) {
  const types = [member.type_primary, member.type_secondary].filter(Boolean) as string[];
  const petData = pets.find((p) => p.id === member.pet_id);
  const statTotal = petData?.stats.total ?? 0;

  return (
    <div className="tc-pet">
      <div className="tc-pet-header">
        <span className="tc-pet-index">#{index + 1}</span>
        <span className="tc-pet-id">No.{member.pet_id}</span>
      </div>
      <div className="tc-pet-name">{member.name}</div>
      <div className="tc-pet-types">
        {types.map((t) => (
          <span key={t} className="type-badge" style={{ background: getTypeColor(t) }}>
            {t}
          </span>
        ))}
      </div>
      <span className="tc-pet-role" style={{ background: getRoleColor(member.role) }}>
        {member.role}
      </span>
      <div className="tc-pet-skills">
        {member.skills.slice(0, 4).map((s) => (
          <span key={s} className="tc-skill-tag">{s}</span>
        ))}
      </div>
      <div className="tc-pet-stats">
        <span className="tc-stat-item">HP {member.stats.hp}</span>
        <span className="tc-stat-item">攻 {member.stats.atk}</span>
        <span className="tc-stat-item">防 {member.stats.def}</span>
        <span className="tc-stat-item">特攻 {member.stats.sp_atk}</span>
        <span className="tc-stat-item">特防 {member.stats.sp_def}</span>
        <span className="tc-stat-item">速 {member.stats.speed}</span>
      </div>
      <span className="tc-pet-total">种族值 {statTotal}</span>
    </div>
  );
}

function ScoreBar({ value, max, label }: { value: number; max: number; label: string }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div className="tc-score-row">
      <span className="tc-score-label">{label}</span>
      <div className="tc-score-track">
        <div
          className="tc-score-fill"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="tc-score-val">{value.toFixed(1)}</span>
    </div>
  );
}

export default function TeamCard({ result, rank }: Props) {
  const { team, scores } = result;

  return (
    <div className="team-card">
      {/* 头部 */}
      <div className="tc-header">
        <div className="tc-rank">
          <span className="tc-rank-num">#{rank}</span>
          <span className="tc-rank-total">{scores.total.toFixed(0)} 分</span>
        </div>
        <div className="tc-actions">
          <a
            className="btn btn-small btn-secondary"
            href={`/team-builder?ids=${team.map((m) => m.pet_id).join(",")}`}
          >
            导入编队
          </a>
        </div>
      </div>

      {/* 精灵列表 */}
      <div className="tc-pets">
        {team.map((member, i) => (
          <PetMini key={member.pet_id + "_" + i} member={member} index={i} />
        ))}
      </div>

      {/* 评分条 */}
      <div className="tc-scores">
        {SCORE_META.map(({ key, label, max }) => (
          <ScoreBar key={key} value={scores[key]} max={max} label={label} />
        ))}
      </div>
    </div>
  );
}

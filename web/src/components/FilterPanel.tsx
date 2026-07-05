import { TYPES } from "../types";
import { getTypeColor } from "../utils/typeChart";

interface Props {
  selected: string[];
  onToggle: (type: string) => void;
  sortBy: string;
  onSortChange: (sort: string) => void;
}

export default function FilterPanel({ selected, onToggle, sortBy, onSortChange }: Props) {
  return (
    <div className="filter-row">
      <button
        className={`filter-chip ${!selected.length ? "selected" : ""}`}
        onClick={() => {}}
      >
        全部
      </button>
      {TYPES.map((t) => (
        <button
          key={t}
          className={`filter-chip ${selected.includes(t) ? "selected" : ""}`}
          style={
            selected.includes(t)
              ? { background: getTypeColor(t), borderColor: getTypeColor(t) }
              : {}
          }
          onClick={() => onToggle(t)}
        >
          {t}
        </button>
      ))}
      <select
        className="sort-select"
        value={sortBy}
        onChange={(e) => onSortChange(e.target.value)}
      >
        <option value="id">编号排序</option>
        <option value="total_desc">种族值↓</option>
        <option value="total_asc">种族值↑</option>
        <option value="name">名称排序</option>
        <option value="hp_desc">生命↓</option>
        <option value="atk_desc">物攻↓</option>
        <option value="sp_atk_desc">魔攻↓</option>
        <option value="speed_desc">速度↓</option>
      </select>
    </div>
  );
}

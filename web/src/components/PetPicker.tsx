import { useState, useMemo } from "react";
import type { Pet } from "../types";
import { pets } from "../data";
import { getTypeColor } from "../utils/typeChart";

interface Props {
  onSelect: (pet: Pet) => void;
  onClose: () => void;
}

export default function PetPicker({ onSelect, onClose }: Props) {
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    if (!search.trim()) return pets;
    const kw = search.trim().toLowerCase();
    return pets.filter(
      (p) =>
        p.name.toLowerCase().includes(kw) ||
        String(p.id).includes(kw) ||
        p.type_primary.includes(kw)
    );
  }, [search]);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3>选择精灵</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        <div className="search-bar">
          <input
            type="text"
            placeholder="搜索精灵名称、编号、属性..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            autoFocus
          />
        </div>
        <div className="picker-list">
          {filtered.map((pet) => {
            const types = [pet.type_primary, pet.type_secondary].filter(Boolean) as string[];
            return (
              <div
                key={pet.id || pet.name}
                className="picker-item"
                onClick={() => onSelect(pet)}
              >
                <div className="picker-item-left">
                  <span className="picker-item-id">No.{pet.id || "?"}</span>
                  <span className="picker-item-name">{pet.name}</span>
                  <span className="picker-item-types">
                    {types.map((t) => (
                      <span key={t} className="type-badge" style={{ background: getTypeColor(t) }}>
                        {t}
                      </span>
                    ))}
                  </span>
                </div>
                <span className="picker-item-total">{pet.stats.total}</span>
              </div>
            );
          })}
          {filtered.length === 0 && (
            <p style={{ textAlign: "center", color: "var(--text-dim)", padding: 20 }}>
              没有匹配的精灵
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

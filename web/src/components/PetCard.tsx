import type { Pet } from "../types";
import { getTypeColor } from "../utils/typeChart";
import { useNavigate } from "react-router-dom";

export default function PetCard({ pet }: { pet: Pet }) {
  const navigate = useNavigate();
  const types = [pet.type_primary, pet.type_secondary].filter(Boolean) as string[];

  return (
    <div className="pet-card" onClick={() => navigate(`/pet/${pet.id}`)}>
      <div className="pet-card-number">No.{pet.id || "???"}</div>
      <div className="pet-card-name">{pet.name}</div>
      <div className="pet-card-types">
        {types.map((t) => (
          <span key={t} className="type-badge" style={{ background: getTypeColor(t) }}>
            {t}
          </span>
        ))}
      </div>
      <div className="pet-card-total">种族值 {pet.stats.total}</div>
    </div>
  );
}

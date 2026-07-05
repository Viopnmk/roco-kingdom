import { useNavigate } from "react-router-dom";
import type { Pet, PetType } from "../types";
import { getTypeColor } from "../utils/typeChart";

interface EvolutionChain {
  id: string;
  name: string;
  members: Pet[];
  apex_id: number;
  apex_name: string;
}

export default function EvolutionChainCard({ chain }: { chain: EvolutionChain }) {
  const navigate = useNavigate();

  const apexPet = chain.members.find((p) => p.id === chain.apex_id);
  const types = apexPet
    ? [apexPet.type_primary, apexPet.type_secondary].filter(
        (t): t is PetType => t !== undefined
      )
    : [];

  // 获取显示用的家族编号
  const displayNumber = chain.id.replace("family_", "").replace("chain_", "");

  const handleClick = () => {
    navigate(`/chain/${chain.id}`);
  };

  return (
    <div className="evo-chain-card" onClick={handleClick}>
      <div className="evo-card-number">家族 #{displayNumber.padStart(3, "0")}</div>
      <div className="evo-card-name">{chain.name}</div>
      <div className="evo-card-types">
        {types.map((t) => (
          <span key={t} className="type-badge" style={{ background: getTypeColor(t) }}>
            {t}
          </span>
        ))}
      </div>
      <div className="evo-card-count">共 {chain.members.length} 只精灵</div>
      <div className="evo-card-arrow">→ 查看详情</div>
    </div>
  );
}